#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

try:
    import boto3
except ImportError:
    sys.stderr.write('boto3 is not installed. Install with the following command:\n    python3 -m pip install boto3')
    exit()

AWS_REGION = os.getenv('SAFEAWS_REGION') or os.getenv('AWS_REGION') or 'us-east-1'
AWS_PROFILE = os.getenv('SAFEAWS_PROFILE') or os.getenv('AWS_PROFILE')
BEDROCK_MODEL_ID = os.getenv('SAFEAWS_BEDROCK_MODEL_ID') or 'anthropic.claude-3-haiku-20240307-v1:0'
ANTHROPIC_VERSION = os.getenv('SAFEAWS_ANTHROPIC_VERSION') or 'bedrock-2023-05-31'
MODEL_MAX_TOKENS = os.getenv('SAFEAWS_MODEL_MAX_TOKENS') or 1024
TEMPERATURE = os.getenv('SAFEAWS_TEMPERATURE') or 0.5

PROMPT_TEMPLATE = '''{help_text}
---
Command with arguments:
aws {command}

Based on the help text provided w.r.t to the command to be called,
please review the command arguments above which will be executed as-is:
- Verify if the default values/handling for any unspecified attributes or parameters are appropriate or if they need to be explicitly set.
- Check if any required attributes or parameters are missing from the command
- Identify any sensitive or critical attributes that should not be left to default values and ensure they are explicitly specified in the command.
- Check if the command includes any attributes or parameters that might override existing configurations or settings unintentionally.
- Verify if the command includes any attributes or parameters that might have unintended consequences or side effects when set to their default values.
- Identify if any attributes or parameters related to security, compliance, or data protection are being left to default values, which could potentially introduce vulnerabilities or risks.

No need to warn about IAM permissions,
Be precise, do not address anything that is valid,
just use point form padded with newlines to highlight potential issues.
output the results in plain text, assuming a CLI environment.'''

boto3_session = boto3.Session(profile_name=AWS_PROFILE)
bedrock_client = boto3_session.client(
    service_name='bedrock-runtime',
    region_name=AWS_REGION,
)

# Set up the CLI parser
parser = argparse.ArgumentParser(description="Safely execute AWS CLI commands with AI check.")
parser.add_argument('command', nargs=argparse.REMAINDER, help='The AWS CLI command to execute')


class HelpTextError(Exception):
    pass


class AwsCommandError(Exception):
    pass


def _clean_raw_aws_help_output(raw_help_output: str) -> str:
    output = ''

    in_shorthand_syntax = False
    in_json_syntax = False

    for l in raw_help_output.split('\n'):
        if '\b' in l:
            # l = re.sub(r'_\x08', '', l)
            l = re.sub(r'.\x08', '', l)

        if l.endswith('Shorthand Syntax:'):
            in_shorthand_syntax = True
            block_indent = len(l) - len(l.lstrip())
            continue
        elif l.endswith('JSON Syntax:'):
            in_json_syntax = True
            block_indent = len(l) - len(l.lstrip())
            continue

        if (in_shorthand_syntax or in_json_syntax):
            if l.strip() == '':
                continue
            else:
                len_leading_spaces = len(l) - len(l.lstrip())
                if len_leading_spaces <= block_indent:
                    in_shorthand_syntax = False
                    in_json_syntax = False
                    block_indent = 0
                else:
                    continue

        if l.strip() == '':
            continue

        output += l + '\n'

    # Remove all sections from 'GLOBAL OPTIONS' onwards
    output = output.split('GLOBAL OPTIONS')[0]
    # Remove cli input docs
    output = output.split('       --cli-input-json | --cli-input-yaml')[0]

    return output


def get_aws_cli_help(command: list[str]) -> str:
    try:
        env = os.environ.copy()
        env['AWS_PAGER'] = ''
        raw_help_output = subprocess.check_output(
            ['aws', *command, 'help'],
            text=True,
            env=env,
            # ignore stderr
            stderr=subprocess.DEVNULL,
        )
        return _clean_raw_aws_help_output(raw_help_output)
    except subprocess.CalledProcessError as e:
        error_message = f"Error getting AWS CLI help for command: `{' '.join(command)}`\n" + e.output
        sys.stderr.write(error_message)
        raise HelpTextError(error_message)


def check_command_with_ai(command: list[str], help_text: str) -> bool:
    prompt = PROMPT_TEMPLATE.format(
        help_text=help_text,
        command=' '.join(command),
    )
    body = {
        'anthropic_version': ANTHROPIC_VERSION,
        'max_tokens': MODEL_MAX_TOKENS,
        'temperature': TEMPERATURE,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt}
                ]
            }
        ],
    }
    response = bedrock_client.invoke_model_with_response_stream(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(body),
    )

    for event in response.get('body'):
        chunk = json.loads(event['chunk']['bytes'])
        if chunk['type'] == 'content_block_delta':
            if chunk['delta']['type'] == 'text_delta':
                sys.stdout.write(chunk['delta']['text'])

    # Prompt the user to confirm command execution
    user_input = input('\n\nDo you want to execute the command? (y/N) ')
    return user_input.lower() == 'y'


def execute_command(command: list[str]):
    try:
        subprocess.run(['aws'] + command, check=True)
        sys.stdout.write(f"Command '{' '.join(command)}' executed successfully.\n")
    except subprocess.CalledProcessError as e:
        raise AwsCommandError from e


def main():
    args = parser.parse_args()
    command: list[str] = args.command

    if len(command) < 2:
        sys.stderr.write('Error: No valid AWS CLI command provided. Exiting.\n')
        return

    # Get the AWS CLI help text for the command
    try:
        help_text = get_aws_cli_help(command[:2])
    except HelpTextError:
        exit(1)

    if help_text is None:
        sys.stdout.write('Error getting AWS CLI help text. Exiting.\n')
        return

    # Check the command with the AI model
    execute = check_command_with_ai(command, help_text)

    if not execute:
        exit()

    try:
        execute_command(command)
    except AwsCommandError:
        exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit()
