import tkinter as tk
import os
import getpass
import subprocess

def show_system():
    label.config(text=f"User: {getpass.getuser()}")

def show_kernel():
    kernel = os.popen("uname -r").read().strip()
    label.config(text=f"Kernel: {kernel}")

def show_cpu():
    cpu = os.popen("grep 'model name' /proc/cpuinfo | head -1").read()
    label.config(text=cpu.strip())

def show_ram():
    ram = subprocess.check_output("free -h", shell=True).decode().splitlines()[1]
    label.config(text=f"RAM: {ram}")

def update_ram():
    ram = subprocess.check_output("free -h", shell=True).decode().splitlines()[1]
    label.config(text=f"RAM: {ram}")
    root.after(1000, update_ram)

def show_ip():
    ip = subprocess.check_output("hostname -I", shell=True).decode().strip()
    label.config(text=f"IP: {ip}")

def test():
    print("Button works")

root = tk.Tk()
root.title("System Dashboard")
root.geometry("400x400")

title = tk.Label(root, text="Device Info", font=("Arial", 10))
title.pack(pady=10)

btn1 = tk.Button(root, text="Show User", command=show_system)
btn1.pack(pady=5)

btn2 = tk.Button(root, text="Show Kernel Version", command=show_kernel)
btn2.pack(pady=5)

btn3 = tk.Button(root, text="Show CPU", command=show_cpu)
btn3.pack(pady=5)

btn4 = tk.Button(root, text="Show RAM Usage", command=show_ram)
btn4.pack(pady=5)

btn5 = tk.Button(root, text="Show Network IP", command=show_ip)
btn5.pack(pady=5)

btn_test = tk.Button(root, text="Test", command=test)
btn_test.pack(pady=5)

label = tk.Label(root, text="Ready")
label.pack(pady=20)

root.mainloop()
