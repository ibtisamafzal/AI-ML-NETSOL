# Stack
stack = []
stack.append(1)
stack.append(2)
stack.append(3)
print(stack.pop())


# Queue
from collections import deque
import heapq
queue = deque()
queue.append(1)
queue.append(2)
queue.append(3)
print(queue.popleft())


# Linked List
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

node1 = Node(1)
node2 = Node(2)
node3 = Node(3)
node1.next = node2
node2.next = node3
print(node1.data)
print(node2.data)
print(node3.data)

# Doubly Linked List Example - Picture Gallery Next-Previous buttons

# Tree
# Binary Tree Example - At most 2 children.
# Binary Search Tree Example - Left child < Parent < Right child.


# Graph
# Weighted Graph
# Directed Graph
# Undirected Graph

# Dictionary of Lists Representation of a Graph
graph = {
    "A": ["B", "C"],
    "B": ["A", "D"],
    "C": ["A", "D"],
    "D": ["B", "C"]
    }



# Hash Table
# Hash Function
# Hashing

# Heap - Priority Queue
import heapq

