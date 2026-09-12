resource "aws_cloudwatch_log_group" "api" {
  name = "/ecs/launchforge-api"

  tags = {
    Name    = "${var.project_name}-api-logs"
    Project = var.project_name
  }
}