#!/bin/bash
let x=0
if test $# -eq 0
then
	echo "commit.sh: Meteme el mensaje para el comit entre comillas dobles \"\" "
	exit
else
  
	if [[ $1 == "-x" ]]
	then
		let x=1 
	fi
	if test $# -gt 2 
		then
			echo "demasiados argumentos"
			exit
	fi
fi

echo "usuario github:	vendul0g"
echo "token github: 		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"

git add -A
git commit -m "$1"
git push -u origin main

