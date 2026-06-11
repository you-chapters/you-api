from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class DynamoDBStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table_kwargs = dict(
            partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="entry_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.entries_table = dynamodb.Table(
            self,
            "EntriesTable",
            table_name="entries",
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            **table_kwargs,
        )

        self.test_table = dynamodb.Table(self, "TestEntriesTable", table_name="test_entries", **table_kwargs)

        timestamp_gsi = dict(
            index_name="user_timestamp_index",
            partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.entries_table.add_global_secondary_index(**timestamp_gsi)
        self.test_table.add_global_secondary_index(**timestamp_gsi)

        self.narratives_table = dynamodb.Table(
            self,
            "NarrativesTable",
            table_name="narratives",
            partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="record_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
