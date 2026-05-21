import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.cognito_stack import CognitoStack
from stacks.dynamodb_stack import DynamoDBStack

app = cdk.App()

dynamo_stack = DynamoDBStack(app, "YouApiDynamoDBStack")
cognito_stack = CognitoStack(app, "YouApiCognitoStack")
ApiStack(app, "YouApiApiStack", entries_table=dynamo_stack.entries_table, narratives_table=dynamo_stack.narratives_table,
         user_pool=cognito_stack.user_pool)

app.synth()
