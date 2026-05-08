from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, table: dynamodb.Table, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = PythonFunction(
            self,
            "YouApiFunction",
            entry=str(REPO_ROOT / "app"),
            index="handler.py",
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

        apigw.LambdaRestApi(
            self,
            "YouApiRestApi",
            handler=fn,
        )
