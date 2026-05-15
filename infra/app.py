import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.cognito_stack import CognitoStack
from stacks.dynamodb_stack import DynamoDBStack

app = cdk.App()

dynamo_stack = DynamoDBStack(app, "YouApiDynamoDBStack")
cognito_stack = CognitoStack(app, "YouApiCognitoStack")
ApiStack(app, "YouApiApiStack", table=dynamo_stack.table, user_pool=cognito_stack.user_pool)

app.synth()
