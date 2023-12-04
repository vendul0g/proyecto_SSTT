#!/bin/bash
let x=0
if test $# -eq 0
then
	echo "commit.sh: Meteme el mensaje para el comit entre comillas dobles \"\" "
	exit
else
  
	if test $# -gt 1 
		then
			echo "demasiados argumentos"
			exit
	fi
fi

git add -A
git commit -m "$1"
git push -u origin main

