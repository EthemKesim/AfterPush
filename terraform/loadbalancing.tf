resource "aws_lb" "main" {
  name                       = "launchforge-alb"
  internal                   = var.alb_access_mode == "internal"
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

  lifecycle {
    precondition {
      condition = (
        var.alb_access_mode == "internal" ||
        length(var.public_alb_ingress_cidrs) > 0
      )
      error_message = "Public ALB access requires an explicit non-empty public_alb_ingress_cidrs allowlist."
    }
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

resource "aws_lb_target_group" "api_green" {
  name        = "launchforge-green-tg"
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
    Name    = "${var.project_name}-green-tg"
    Project = var.project_name
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.acm_certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener_rule" "production" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type = "forward"

    forward {
      target_group {
        arn    = aws_lb_target_group.api.arn
        weight = 1
      }

      target_group {
        arn    = aws_lb_target_group.api_green.arn
        weight = 0
      }
    }
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}
