resource "aws_ecr_repository" "api" {
  name                 = "afterpush-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "afterpush-api"
  }
}
