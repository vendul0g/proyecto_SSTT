# coding=utf-8
#!/usr/bin/env python3

import sys 

def main():
    txt = "a.navarromartinez1@um.es"
    x = txt.encode('utf-8')
    print(x)
    print(x.decode('utf-8')) 


if __name__ == "__main__":
    main()