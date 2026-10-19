resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"

        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          title  = "ECS CPU Utilization"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Average"

          metrics = [
            [
              "AWS/ECS",
              "CPUUtilization",
              "ClusterName",
              aws_ecs_cluster.main.name,
              "ServiceName",
              aws_ecs_service.api.name
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          title  = "ECS Memory Utilization"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Average"

          metrics = [
            [
              "AWS/ECS",
              "MemoryUtilization",
              "ClusterName",
              aws_ecs_cluster.main.name,
              "ServiceName",
              aws_ecs_service.api.name
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 0
        y      = 6
        width  = 8
        height = 6

        properties = {
          title  = "ALB Request Count"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Sum"

          metrics = [
            [
              "AWS/ApplicationELB",
              "RequestCount",
              "LoadBalancer",
              aws_lb.main.arn_suffix
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 8
        y      = 6
        width  = 8
        height = 6

        properties = {
          title  = "ALB Target Response Time"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Average"

          metrics = [
            [
              "AWS/ApplicationELB",
              "TargetResponseTime",
              "LoadBalancer",
              aws_lb.main.arn_suffix
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 16
        y      = 6
        width  = 8
        height = 6

        properties = {
          title  = "Target HTTP 5XX Errors"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Sum"

          metrics = [
            [
              "AWS/ApplicationELB",
              "HTTPCode_Target_5XX_Count",
              "LoadBalancer",
              aws_lb.main.arn_suffix
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          title  = "ALB Healthy Targets"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Average"

          metrics = [
            [
              "AWS/ApplicationELB",
              "HealthyHostCount",
              "TargetGroup",
              aws_lb_target_group.api.arn_suffix,
              "LoadBalancer",
              aws_lb.main.arn_suffix
            ]
          ]
        }
      },
      {
        type = "metric"

        x      = 12
        y      = 12
        width  = 12
        height = 6

        properties = {
          title  = "ALB Unhealthy Targets"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Average"

          metrics = [
            [
              "AWS/ApplicationELB",
              "UnHealthyHostCount",
              "TargetGroup",
              aws_lb_target_group.api.arn_suffix,
              "LoadBalancer",
              aws_lb.main.arn_suffix
            ]
          ]
        }
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  alerts_topic_arn     = "arn:${data.aws_partition.current.partition}:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-alerts"
  target_5xx_alarm_arn = "arn:${data.aws_partition.current.partition}:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${var.project_name}-target-5xx"
}

data "aws_iam_policy_document" "alerts_kms" {
  statement {
    sid    = "EnableAccountRootAdministration"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowSnsForThisTopic"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:sns:topicArn"
      values   = [local.alerts_topic_arn]
    }
  }

  statement {
    sid    = "AllowTarget5xxAlarmToPublish"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [local.target_5xx_alarm_arn]
    }
  }
}

resource "aws_kms_key" "alerts" {
  description             = "Encrypts messages for the ${var.project_name} alerts SNS topic"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.alerts_kms.json

  tags = {
    Name    = "${var.project_name}-alerts-kms"
    Project = var.project_name
  }
}

resource "aws_kms_alias" "alerts" {
  name          = "alias/${var.project_name}-alerts"
  target_key_id = aws_kms_key.alerts.key_id
}

resource "aws_sns_topic" "alerts" {
  name              = "${var.project_name}-alerts"
  kms_master_key_id = aws_kms_key.alerts.arn

  tags = {
    Name    = "${var.project_name}-alerts"
    Project = var.project_name
  }
}

resource "aws_cloudwatch_metric_alarm" "target_5xx" {
  alarm_name        = "${var.project_name}-target-5xx"
  alarm_description = "Triggers when the AfterPush application returns HTTP 5XX responses."

  namespace   = "AWS/ApplicationELB"
  metric_name = "HTTPCode_Target_5XX_Count"

  statistic = "Sum"
  period    = 60

  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"

  evaluation_periods = 1

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }

  treat_missing_data = "notBreaching"

  alarm_actions = [
    aws_sns_topic.alerts.arn
  ]

  tags = {
    Name    = "${var.project_name}-target-5xx-alarm"
    Project = var.project_name
  }
}

resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
