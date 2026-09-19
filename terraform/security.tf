resource "aws_security_group" "alb" {
  name        = "launchforge-alb-sg"
  description = "Security group for LaunchForge ALB"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-alb-sg"
    Project = var.project_name
  }
}

resource "aws_security_group" "ecs" {
  name        = "launchforge-ecs-sg"
  description = "Security group for LaunchForge ECS tasks"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-ecs-sg"
    Project = var.project_name
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id

  cidr_ipv4   = "0.0.0.0/0"
  from_port   = 80
  to_port     = 80
  ip_protocol = "tcp"

  description = "Allow HTTP traffic from the internet"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id = aws_security_group.ecs.id

  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"

  description = "Allow application traffic only from the ALB"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id = aws_security_group.alb.id

  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"

  description = "Allow ALB traffic to ECS tasks on port 3000"
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = aws_security_group.ecs.id

  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "-1"

  description = "Allow all outbound traffic"
}

resource "aws_security_group" "vpc_endpoints" {
  name        = "launchforge-vpc-endpoints-sg"
  description = "Security group for VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-vpc-endpoints-sg"
    Project = var.project_name
  }
}

resource "aws_vpc_security_group_ingress_rule" "vpc_endpoints_from_ecs" {
  security_group_id = aws_security_group.vpc_endpoints.id

  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"

  description = "Allow HTTPS traffic from ECS tasks"
}