# Update ECS Task Policy - Manual Instructions

## Issue

The ECS Task Role (`MLPlatformECSTaskRole`) is missing some DynamoDB permissions. It currently only has:

- `dynamodb:GetItem`
- `dynamodb:PutItem`
- `dynamodb:UpdateItem`

But it needs:

- `dynamodb:Scan`
- `dynamodb:Query`
- `dynamodb:DescribeTable`

## Solution

You need to update the `MLPlatformECSTaskPolicy` to include all DynamoDB permissions. This requires IAM admin permissions.

### Option 1: AWS Console (Easiest)

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click **Policies** in the left menu
3. Search for `MLPlatformECSTaskPolicy`
4. Click on the policy
5. Click **Edit policy**
6. Click on the **JSON** tab
7. Find the DynamoDB statement and update it to:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:Scan",
    "dynamodb:Query",
    "dynamodb:DescribeTable"
  ],
  "Resource": "arn:aws:dynamodb:us-east-1:618574523116:table/ml-jobs"
}
```

8. Click **Review policy**
9. Click **Save changes**

### Option 2: AWS CLI (Requires IAM Admin)

```bash
# Load environment variables
source .env

# Create updated policy document
cat > /tmp/ecs-task-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET_NAME}",
                "arn:aws:s3:::${S3_BUCKET_NAME}/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Scan",
                "dynamodb:Query",
                "dynamodb:DescribeTable"
            ],
            "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Get current policy version
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformECSTaskPolicy"
CURRENT_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)

# Create new policy version
aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document file:///tmp/ecs-task-policy.json \
    --set-as-default

# Delete old policy version (optional, but recommended to stay under the 5 version limit)
aws iam delete-policy-version \
    --policy-arn "$POLICY_ARN" \
    --version-id "$CURRENT_VERSION"

echo "✓ Policy updated successfully"
```

### Verify the Update

After updating, run the tests to verify:

```bash
pytest tests/test_ecs_task_dynamodb_permissions.py -v
```

Or check manually:

```bash
aws iam get-policy-version \
    --policy-arn "arn:aws:iam::618574523116:policy/MLPlatformECSTaskPolicy" \
    --version-id $(aws iam get-policy --policy-arn "arn:aws:iam::618574523116:policy/MLPlatformECSTaskPolicy" --query 'Policy.DefaultVersionId' --output text) \
    --query 'PolicyVersion.Document' --output json | jq '.Statement[] | select(.Action[]? | startswith("dynamodb:"))'
```

## Why These Permissions Are Needed

- **dynamodb:GetItem** - Get job details (already present)
- **dynamodb:PutItem** - Create jobs (already present)
- **dynamodb:UpdateItem** - Update job status (already present, CRITICAL for training container)
- **dynamodb:Scan** - List all jobs (needed for future features)
- **dynamodb:Query** - Query jobs by attributes (needed for future features)
- **dynamodb:DescribeTable** - Get table metadata for error handling and diagnostics

## Current Status

Run the test to see what's missing:

```bash
pytest tests/test_ecs_task_dynamodb_permissions.py::TestECSTaskRoleDynamoDBPermissions::test_task_role_has_all_required_permissions -v
```

This will tell you exactly which permissions are missing.
