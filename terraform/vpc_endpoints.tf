# ECR API - ECR API calls without public internet
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids = [
    aws_subnet.main["private-a"].id,
    aws_subnet.main["private-b"].id
  ]

  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]

  tags = {
    Name    = "${var.project_name}-ecr-api-endpoint"
    Project = var.project_name
  }
}

# ECR Docker Registry - Docker image pull traffic
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids = [
    aws_subnet.main["private-a"].id,
    aws_subnet.main["private-b"].id
  ]

  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]

  tags = {
    Name    = "${var.project_name}-ecr-dkr-endpoint"
    Project = var.project_name
  }
}

# CloudWatch Logs - send container logs without public internet
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids = [
    aws_subnet.main["private-a"].id,
    aws_subnet.main["private-b"].id
  ]

  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]

  tags = {
    Name    = "${var.project_name}-logs-endpoint"
    Project = var.project_name
  }
}

# S3 - ECR image layers are stored in S3
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    aws_route_table.private.id
  ]

  tags = {
    Name    = "${var.project_name}-s3-endpoint"
    Project = var.project_name
  }
}