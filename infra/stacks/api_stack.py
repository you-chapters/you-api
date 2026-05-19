from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subs
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, table: dynamodb.Table, user_pool: cognito.UserPool,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        _SSM_OPENAI = "/you-api/openai-api-key"
        _SSM_PINECONE_KEY = "/you-api/pinecone-api-key"
        _SSM_PINECONE_HOST = "/you-api/pinecone-index-host"

        ssm_params = [
            ssm.StringParameter.from_secure_string_parameter_attributes(
                self, "OpenAIApiKeyParam", parameter_name=_SSM_OPENAI
            ),
            ssm.StringParameter.from_secure_string_parameter_attributes(
                self, "PineconeApiKeyParam", parameter_name=_SSM_PINECONE_KEY
            ),
            ssm.StringParameter.from_secure_string_parameter_attributes(
                self, "PineconeIndexHostParam", parameter_name=_SSM_PINECONE_HOST
            ),
        ]

        shared_env = {
            "OPENAI_API_KEY": _SSM_OPENAI,
            "PINECONE_API_KEY": _SSM_PINECONE_KEY,
            "PINECONE_INDEX_HOST": _SSM_PINECONE_HOST,
        }

        fn = PythonFunction(
            self,
            "YouApiFunction",
            entry=str(REPO_ROOT),
            index="app/handler.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            memory_size=512,
            timeout=Duration.seconds(30),
            environment={
                "REPOSITORY_TYPE": "dynamodb",
                "DYNAMODB_TABLE_NAME": table.table_name,
                "EMBEDDING_TYPE": "openai",
                "VECTOR_REPOSITORY_TYPE": "pinecone",
                **shared_env,
            },
        )

        table.grant_read_write_data(fn)
        for param in ssm_params:
            param.grant_read(fn)

        embedding_fn = PythonFunction(
            self,
            "YouEmbeddingFunction",
            entry=str(REPO_ROOT),
            index="app/handler_embedding.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            memory_size=512,
            timeout=Duration.seconds(60),
            environment=shared_env,
        )

        dlq = sqs.Queue(
            self,
            "EmbeddingDLQ",
            retention_period=Duration.days(14),
        )

        alert_topic = sns.Topic(self, "EmbeddingAlertTopic")
        alert_topic.add_subscription(sns_subs.EmailSubscription("oleksander.havryliuk@gmail.com"))

        cloudwatch.Alarm(
            self,
            "EmbeddingDLQAlarm",
            metric=dlq.metric_approximate_number_of_messages_visible(),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_description="Embedding Lambda failed to process a DynamoDB stream record",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))

        for param in ssm_params:
            param.grant_read(embedding_fn)

        table.grant_stream_read(embedding_fn)
        embedding_fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_error=True,
                on_failure=lambda_event_sources.SqsDlq(dlq),
                max_record_age=Duration.hours(1),
            )
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "YouApiAuthorizer",
            cognito_user_pools=[user_pool],
        )

        apigw.LambdaRestApi(
            self,
            "YouApiRestApi",
            handler=fn,
            deploy_options=apigw.StageOptions(stage_name="api"),
            endpoint_types=[apigw.EndpointType.REGIONAL],
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["https://you.havryliuk.com", "http://localhost:5173"],
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=apigw.Cors.DEFAULT_HEADERS,
            ),
            default_method_options=apigw.MethodOptions(
                authorization_type=apigw.AuthorizationType.COGNITO,
                authorizer=authorizer,
            ),
        )
