# safeaws-cli

An AWS CLI wrapper that helps you avoid common mistakes and pitfalls
with AI checking your command arguments against the command docs

## Dependencies

- macOS / Linux
- Python 3.6+
- boto3
- AWS CLI (Either Python or binary)

## Configuration

Variable | Description | Default
---|---|---
`SAFEAWS_AWS_PROFILE` | AWS profile to use | None
`SAFEAWS_AWS_REGION` | AWS region to use for Bedrock Model | `us-east-1
`SAFEAWS_BEDROCK_MODEL_ID` | Bedrock Model ID to use for AI checking | `anthropic.claude-3-haiku-20240307-v1:0`
`SAFEAWS_ANTHROPIC_VERSION` | Anthropic API version | `bedrock-2023-05-31`
`SAFEAWS_MODEL_MAX_TOKENS` | Maximum tokens to generate | `1024`
`SAFEAWS_TEMPERATURE` | Temperature for LLM | `0.5`

For authenticating against Amazon Bedrock, though not recommended, you could also set AWS access key and secret key in the environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

For security, it's recommended to setup an `sso-session` and use the `AWS_PROFILE` environment variable to authenticate.

## Install

```bash
sudo curl https://raw.githubusercontent.com/gabrielkoo/safeaws-cli/main/safeaws.py -o /usr/local/bin/safeaws && sudo chmod +x /usr/local/bin/safeaws
```
