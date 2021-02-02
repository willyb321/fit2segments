#!/bin/bash
cd /home/willb/media/fit2segments
for i in activities/*.fit;
do
    /usr/bin/python3.8 fit2segments.py -v $i; 
done


