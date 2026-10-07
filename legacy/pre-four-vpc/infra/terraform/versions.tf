terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Dedicated local state for NT531. Keep this file when cleaning up the lab.
  backend "local" {
    path = "nt531.tfstate"
  }
}
