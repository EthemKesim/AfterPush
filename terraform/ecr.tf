resource "aws_ecr_repository" "api" {
  name                 = "launchforge-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name    = "${var.project_name}-api"
    Project = var.project_name
  }
}