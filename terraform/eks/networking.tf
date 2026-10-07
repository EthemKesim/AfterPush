data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "eks" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.cluster_name}-vpc"
  }
}

resource "aws_internet_gateway" "eks" {
  vpc_id = aws_vpc.eks.id

  tags = {
    Name = "${var.cluster_name}-igw"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id = aws_vpc.eks.id

  cidr_block        = "10.20.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  map_public_ip_on_launch = true

  tags = {
    Name = "${var.cluster_name}-public-a"

    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id = aws_vpc.eks.id

  cidr_block        = "10.20.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]

  map_public_ip_on_launch = true

  tags = {
    Name = "${var.cluster_name}-public-b"

    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.eks.id

  tags = {
    Name = "${var.cluster_name}-public-rt"
  }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.eks.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}