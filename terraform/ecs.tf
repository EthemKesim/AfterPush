resource "aws_ecs_cluster" "main" {
  name = "launchforge-cluster"

  tags = {
    Name    = "${var.project_name}-cluster"
    Project = var.project_name
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "launchforge-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "launchforge-api"
      image     = "${aws_ecr_repository.api.repository_url}:v1"
      cpu       = 0
      essential = true

      portMappings = [
        {
          containerPort = 3000
          hostPort      = 3000
          protocol      = "tcp"
        }
      ]

      environment = []

      mountPoints = []

      volumesFrom = []

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }

      systemControls = []
    }
  ])

  tags = {
    Name    = "${var.project_name}-api-task"
    Project = var.project_name
  }
}

resource "aws_ecs_service" "api" {
  name            = "launchforge-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "${aws_ecs_task_definition.api.family}:${aws_ecs_task_definition.api.revision}"

  desired_count = 1
  launch_type   = "FARGATE"

  platform_version              = "1.4.0"
  availability_zone_rebalancing = "ENABLED"

  health_check_grace_period_seconds = 30

  deployment_configuration {
    strategy             = "BLUE_GREEN"
    bake_time_in_minutes = 2
  }

  network_configuration {
    subnets = [
      aws_subnet.main["private-a"].id,
      aws_subnet.main["private-b"].id
    ]

    security_groups = [
      aws_security_group.ecs.id
    ]

    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "launchforge-api"
    container_port   = 3000

    advanced_configuration {
      alternate_target_group_arn = aws_lb_target_group.api_green.arn
      production_listener_rule   = aws_lb_listener_rule.production.arn
      role_arn                   = aws_iam_role.ecs_infrastructure_lb.arn
    }
  }

  tags = {
    Name    = "${var.project_name}-api-service"
    Project = var.project_name
  }

  lifecycle {
    ignore_changes = [
      task_definition,
      desired_count
    ]
  }
}