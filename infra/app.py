import aws_cdk as cdk

from stacks.api_stack import ApiStack, ApiStackProps
from stacks.cognito_stack import CognitoStack
from stacks.dynamodb_stack import DynamoDBStack

app = cdk.App()

dynamo_stack = DynamoDBStack(app, "YouApiDynamoDBStack")
cognito_stack = CognitoStack(app, "YouApiCognitoStack")

api_props = ApiStackProps(
    entries_table=dynamo_stack.entries_table,
    narratives_table=dynamo_stack.narratives_table,
    ai_rate_limits_table=dynamo_stack.ai_rate_limits_table,
    user_pool=cognito_stack.user_pool,
)
ApiStack(app, "YouApiApiStack", props=api_props)

app.synth()
