import copy 
"""This is a sample python code to test my copy,and referencing concepts"""
data = [10,20,30]
ref = data
copy_data = copy.copy(data)
ref[0] = 100
print(f"Data = {data},ref = {ref},copyData = {copy_data} with ids of data: {id(data)} and id of ref: {id(ref)} and id of copy_data: {id(copy_data)}")
x=10
y=x
y=y+1
print(f"x is {x} {id(x)} \n and y is {y} with id: {id(y)}")
print(f"x is y:{x is (y-1)} ")
#It returns true because the int is small