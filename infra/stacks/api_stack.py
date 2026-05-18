from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, table: dynamodb.Table, user_pool: cognito.UserPool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
            },
        )

        table.grant_read_write_data(fn)

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
