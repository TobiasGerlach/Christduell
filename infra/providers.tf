terraform {
  required_version = ">= 1.13"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state in Azure Storage — bootstrap the storage account once (e.g. via
  # `az group create` + `az storage account create` + `az storage container create`),
  # then uncomment and fill this in. Until then, state is kept locally.
  #
  backend "azurerm" {
    resource_group_name  = "christduell-tfstate-rg"
    storage_account_name = "christduelltfstate"
    container_name       = "tfstate"
    key                  = "christduell.tfstate"
  }
}

provider "azurerm" {
  features {}
}
