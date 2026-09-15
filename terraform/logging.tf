resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/launchforge-api"
  retention_in_days = 14

  tags = {
    Name    = "${var.project_name}-api-logs"
    Project = var.project_name
  }
}