#!/bin/bash

git add .
read -p "Commit description: " desc
git commit -m "$desc"
git push -u origin main
#git remote add origin https://github.com/vendul0g/proyecto_SSTT.git
