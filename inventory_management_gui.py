import tkinter as tk
from tkinter import messagebox

inventory = {}

def add_item():
    name = entry_name.get().strip()
    try:
        qty = int(entry_qty.get())
        price = float(entry_price.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter valid quantity and price!")
        return

    if not name:
        messagebox.showerror("Error", "Please enter a product name!")
        return

    if name in inventory:
        inventory[name]['qty'] += qty
        inventory[name]['price'] = price
    else:
        inventory[name] = {'qty': qty, 'price': price}

    messagebox.showinfo("Success", f"Added/Updated {name} with qty {qty} and price {price:.2f}")
    refresh_inventory()

def sell_item():
    name = entry_name.get().strip()
    try:
        qty = int(entry_qty.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid quantity!")
        return
    if name not in inventory:
        messagebox.showerror("Error", "Item not found!")
        return
    if qty > inventory[name]['qty']:
        messagebox.showerror("Error", "Not enough stock!")
        return

    inventory[name]['qty'] -= qty
    total = qty * inventory[name]['price']
    if inventory[name]['qty'] == 0:
        del inventory[name]
        messagebox.showinfo("Sold", f"Sold {qty} {name}(s) for ${total:.2f}\n{name} is now out of stock.")
    else:
        messagebox.showinfo("Sold", f"Sold {qty} {name}(s) for ${total:.2f}")
    refresh_inventory()

def refresh_inventory():
    text_inventory.delete("1.0", tk.END)
    if not inventory:
        text_inventory.insert(tk.END, "Inventory is empty.\n")
        return
    text_inventory.insert(tk.END, f"{'Product':<15}{'Qty':<10}{'Price':<10}\n")
    text_inventory.insert(tk.END, "-"*35 + "\n")
    for name, data in inventory.items():
        text_inventory.insert(tk.END, f"{name:<15}{data['qty']:<10}{data['price']:<10.2f}\n")

# GUI Setup
root = tk.Tk()
root.title("Inventory Management System")

# Input fields
frame_input = tk.Frame(root)
frame_input.pack(pady=10)

tk.Label(frame_input, text="Product Name:").grid(row=0, column=0, padx=5, pady=5)
entry_name = tk.Entry(frame_input)
entry_name.grid(row=0, column=1, padx=5, pady=5)

tk.Label(frame_input, text="Quantity:").grid(row=1, column=0, padx=5, pady=5)
entry_qty = tk.Entry(frame_input)
entry_qty.grid(row=1, column=1, padx=5, pady=5)

tk.Label(frame_input, text="Price:").grid(row=2, column=0, padx=5, pady=5)
entry_price = tk.Entry(frame_input)
entry_price.grid(row=2, column=1, padx=5, pady=5)

# Buttons
frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

tk.Button(frame_buttons, text="Add / Update Item", command=add_item).grid(row=0, column=0, padx=5)
tk.Button(frame_buttons, text="Sell Item", command=sell_item).grid(row=0, column=1, padx=5)
tk.Button(frame_buttons, text="Exit", command=root.quit).grid(row=0, column=2, padx=5)

# Inventory display
frame_display = tk.Frame(root)
frame_display.pack(pady=10)

tk.Label(frame_display, text="Current Inventory:").pack()
text_inventory = tk.Text(frame_display, width=40, height=10)
text_inventory.pack()

refresh_inventory()
root.mainloop()
