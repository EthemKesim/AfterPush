# AfterPush

AfterPush is an advanced Cloud & DevOps learning project focused on building a production-style application deployment platform on AWS.

The goal of this project is not only to deploy an application, but to understand how modern cloud infrastructure, containerization, networking, infrastructure automation and CI/CD pipelines work together in a real-world architecture.

## Project Goals

* Build and deploy containerized applications on AWS
* Learn Docker and container lifecycle
* Design AWS networking from scratch using VPC and Subnets
* Deploy applications with Amazon ECS and AWS Fargate
* Configure Application Load Balancer and health checks
* Implement Infrastructure as Code with Terraform
* Build a complete CI/CD pipeline using GitHub Actions
* Improve observability, logging and monitoring with AWS services
* Progress toward Kubernetes and advanced DevOps practices

## Current Architecture

<svg viewBox="0 0 320 500" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=500 rx=18 fill="#F8FAFC" stroke="#E5E7EB"/>
  <rect x=78 y=18 width=164 height=36 rx=10 fill="#FFFFFF" stroke="#D1D5DB"/>
  <text x=160 y=40 fontFamily=Arial fontSize=12 fill="#111827" fontWeight="bold" textAnchor="middle">
    Developer
  </text>
  <text x=160 y=50 fontFamily=Arial fontSize=8 fill="#6B7280" textAnchor="middle">
    Git Push
  </text>
  <path d="M160 54 V68" stroke="#9CA3AF" strokeWidth=1.5 strokeLinecap="round"/>
  <polygon points="156,64 164,64 160,70" fill="#9CA3AF"/>
  <rect x=52 y=70 width=216 height=46 rx=10 fill="#E0F2FE" stroke="#7DD3FC"/>
  <text x=160 y=89 fontFamily=Arial fontSize=12 fill="#075985" fontWeight="bold" textAnchor="middle">
    Docker Image
  </text>
  <text x=160 y=102 fontFamily=Arial fontSize=9 fill="#0369A1" textAnchor="middle">
    afterpush-api:v1
  </text>
  <path d="M160 116 V130" stroke="#9CA3AF" strokeWidth=1.5 strokeLinecap="round"/>
  <polygon points="156,126 164,126 160,132" fill="#9CA3AF"/>
  <rect x=52 y=132 width=216 height=46 rx=10 fill="#F3E8FF" stroke="#C4B5FD"/>
  <text x=160 y=151 fontFamily=Arial fontSize=12 fill="#5B21B6" fontWeight="bold" textAnchor="middle">
    Amazon ECR
  </text>
  <text x=160 y=164 fontFamily=Arial fontSize=9 fill="#6D28D9" textAnchor="middle">
    Container Registry
  </text>
  <path d="M160 178 V192" stroke="#9CA3AF" strokeWidth=1.5 strokeLinecap="round"/>
  <polygon points="156,188 164,188 160,194" fill="#9CA3AF"/>
  <rect x=40 y=194 width=240 height=112 rx=12 fill="#ECFDF5" stroke="#86EFAC"/>
  <text x=160 y=212 fontFamily=Arial fontSize=12 fill="#166534" fontWeight="bold" textAnchor="middle">
    AWS VPC
  </text>
  <rect x=52 y=224 width=96 height=66 rx=8 fill="#DBEAFE" stroke="#93C5FD"/>
  <text x=100 y=238 fontFamily=Arial fontSize=9 fill="#1D4ED8" fontWeight="bold" textAnchor="middle">
    Public
  </text>
  <text x=100 y=250 fontFamily=Arial fontSize=8 fill="#1E40AF" textAnchor="middle">
    ALB
  </text>
  <text x=100 y=260 fontFamily=Arial fontSize=8 fill="#1E40AF" textAnchor="middle">
    Listener :80
  </text>
  <rect x=172 y=224 width=96 height=66 rx=8 fill="#D1FAE5" stroke="#6EE7B7"/>
  <text x=220 y=238 fontFamily=Arial fontSize=9 fill="#047857" fontWeight="bold" textAnchor="middle">
    ECS/Fargate
  </text>
  <text x=220 y=250 fontFamily=Arial fontSize=8 fill="#065F46" textAnchor="middle">
    Task
  </text>
  <text x=220 y=260 fontFamily=Arial fontSize=8 fill="#065F46" textAnchor="middle">
    Port 3000
  </text>
  <path d="M148 257 H172" stroke="#64748B" strokeWidth=1.5 strokeDasharray="4 4" strokeLinecap="round"/>
  <polygon points="168,253 176,257 168,261" fill="#64748B"/>
  <text x=160 y=278 fontFamily=Arial fontSize=7 fill="#475569" textAnchor="middle">
    Target Group + Health Check
  </text>
  <path d="M160 306 V320" stroke="#9CA3AF" strokeWidth=1.5 strokeLinecap="round"/>
  <polygon points="156,316 164,316 160,322" fill="#9CA3AF"/>
  <rect x=52 y=322 width=216 height=46 rx=10 fill="#FDE68A" stroke="#F59E0B"/>
  <text x=160 y=341 fontFamily=Arial fontSize=12 fill="#92400E" fontWeight="bold" textAnchor="middle">
    CloudWatch Logs
  </text>
  <text x=160 y=354 fontFamily=Arial fontSize=9 fill="#92400E" textAnchor="middle">
    Centralized logging
  </text>
  <path d="M160 368 V382" stroke="#9CA3AF" strokeWidth=1.5 strokeLinecap="round"/>
  <polygon points="156,378 164,378 160,384" fill="#9CA3AF"/>
  <rect x=78 y=384 width=164 height=36 rx=10 fill="#FFFFFF" stroke="#D1D5DB"/>
  <text x=160 y=400 fontFamily=Arial fontSize=11 fill="#111827" fontWeight="bold" textAnchor="middle">
    Internet Users
  </text>
  <text x=160 y=410 fontFamily=Arial fontSize=8 fill="#6B7280" textAnchor="middle">
    HTTP Requests
  </text>
  <text x=160 y=438 fontFamily=Arial fontSize=10 fill="#374151" fontWeight="bold" textAnchor="middle">
    Security Flow
  </text>
  <text x=160 y=452 fontFamily=Arial fontSize=8 fill="#374151" textAnchor="middle">
    Internet → ALB :80
  </text>
  <text x=160 y=464 fontFamily=Arial fontSize=8 fill="#374151" textAnchor="middle">
    ALB → ECS :3000
  </text>
  <text x=160 y=476 fontFamily=Arial fontSize=8 fill="#374151" textAnchor="middle">
    Health Check → /health
  </text>
</svg>

## How It Works

The application is packaged as a Docker image and pushed to Amazon ECR.

Amazon ECS uses the Task Definition to launch the container on AWS Fargate.

The Application Load Balancer receives HTTP requests from users and forwards them to healthy ECS tasks through the Target Group.

Health checks continuously monitor the `/health` endpoint to ensure traffic is only routed to healthy containers.

## AWS Services Used

* Amazon VPC
* Amazon ECS
* AWS Fargate
* Amazon ECR
* Application Load Balancer
* Target Group
* Security Groups
* IAM
* CloudWatch Logs

## Networking

The project currently uses a custom VPC with four subnets across two Availability Zones.

* Public Subnet A
* Public Subnet B
* Private Subnet A
* Private Subnet B

Current deployment uses the public subnets for the first ECS deployment while private networking improvements will be implemented in later milestones.

## Security

Traffic is restricted using Security Groups.

* Internet can access only the Application Load Balancer on port 80.
* ECS containers accept traffic only from the ALB Security Group on port 3000.
* Containers are not directly exposed through unrestricted inbound rules.

## Local Development

Clone the repository.

```bash
git clone https://github.com/EthemKesim/AfterPush.git
cd AfterPush/app
```

Install dependencies.

```bash
npm install
```

Run the development server.

```bash
npm run dev
```

Test the health endpoint.

```bash
curl http://localhost:3000/health
```

## Docker

Build the Docker image.

```bash
docker build -t afterpush-api:v1 .
```

Run the container locally.

```bash
docker run -p 3000:3000 afterpush-api:v1
```

Verify that the API is running.

```bash
curl http://localhost:3000/health
```

## Deployment Flow

Current manual deployment workflow:

```text
Developer

↓
Docker Build

↓
Amazon ECR

↓
Amazon ECS Task Definition

↓
AWS Fargate

↓
Target Group

↓
Application Load Balancer

↓
Internet
```

Later this workflow will become fully automated using Terraform and GitHub Actions.

## Roadmap

* [x] Node.js + TypeScript API
* [x] Dockerized application
* [x] Amazon ECR repository
* [x] ECS Cluster
* [x] ECS Fargate deployment
* [x] Application Load Balancer
* [x] Target Group and health checks
* [x] CloudWatch logging
* [x] GitHub repository
* [ ] Terraform infrastructure
* [ ] GitHub Actions CI/CD
* [ ] Automatic Docker build & ECR push
* [ ] Automatic ECS deployment
* [ ] Blue/Green deployment
* [ ] Private subnet architecture
* [ ] Kubernetes migration
* [ ] Monitoring and observability stack

## Learning Philosophy

AfterPush is intentionally built step by step instead of using one-click infrastructure.

Every AWS resource is first created manually to understand its purpose, and later the same infrastructure will be recreated using Terraform and automated through CI/CD pipelines.

The objective is to gain practical Cloud and DevOps engineering experience by building a realistic production-style platform from scratch.
