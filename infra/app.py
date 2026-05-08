import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.dynamodb_stack import DynamoDBStack

app = cdk.App()

dynamo_stack = DynamoDBStack(app, "YouApiDynamoDBStack")
ApiStack(app, "YouApiApiStack", table=dynamo_stack.table)

app.synth()
