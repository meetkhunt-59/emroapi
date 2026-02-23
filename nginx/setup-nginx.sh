#!/bin/bash

# Exit on any error
set -e

# Configuration
DOMAIN=""  # Replace with your domain
EMAIL=""  # Replace with your email

# Install Nginx and Certbot
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx

# Create Nginx configuration directory if it doesn't exist
sudo mkdir -p /etc/nginx/sites-available
sudo mkdir -p /etc/nginx/sites-enabled

# Copy Nginx configuration
sudo cp nginx/emroapi.conf /etc/nginx/sites-available/emroapi.conf

# Create symbolic link
sudo ln -sf /etc/nginx/sites-available/emroapi.conf /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

echo "Nginx configuration completed!"
echo "Your API should now be accessible at http://$DOMAIN"