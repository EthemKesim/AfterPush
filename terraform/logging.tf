resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/launchforge-api"
  retention_in_days = 14

  tags = {
    Name    = "${var.project_name}-api-logs"
    Project = var.project_name
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow" {
  name              = "/vpc/${var.project_name}/flow-logs"
  retention_in_days = 30

  tags = {
    Name    = "${var.project_name}-vpc-flow-logs"
    Project = var.project_name
  }
}