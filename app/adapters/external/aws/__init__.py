"""AWS SDK adapters (boto3): SES email sender and Secrets Manager provider.

Every client is initialized with the environment-decided kwargs dict from
the composition root (``aws_client_credentials(app_env)``): development
gets the LocalStack parameterization (``LOCALSTACK_AWS_CREDENTIALS``),
every other environment the basic client — no explicit credentials (IAM
credential chain) and no endpoint override. The URL lives inside the dict,
not in the adapters.
"""