resource "aws_lb" "main" {
  name                       = "launchforge-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true

  subnets = [
    aws_subnet.main["public-a"].id,
    aws_subnet.main["public-b"].id
  ]

  tags = {
    Name    = "${var.project_name}-alb"
    Project = var.project_name
  }
}

resource "aws_lb_target_group" "api" {
  name        = "launchforge-tg"
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    healthy_threshold   = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name    = "${var.project_name}-tg"
    Project = var.project_name
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}