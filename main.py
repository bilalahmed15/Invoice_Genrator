from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from selenium import webdriver
import time
import os
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoices.db'
db = SQLAlchemy(app)

secret_key = secrets.token_hex(16)
app.secret_key = secret_key


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    address = db.Column(db.String(200))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime)
    user = db.relationship('User', backref=db.backref('invoices', lazy=True))
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True)

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    description = db.Column(db.String(200))
    unit_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    vat_percentage = db.Column(db.Float)


VALID_CREDENTIALS = {'Hamza1234': 'Macarto1234'}


@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('add_user'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in VALID_CREDENTIALS and VALID_CREDENTIALS[username] == password:
            session['username'] = username
            return redirect(url_for('add_user'))
        else:
            return "Invalid credentials. Please try again."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        user = User(name=name, address=address)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('generate_invoice'))
    return render_template('generate_invoice.html')

@app.route('/generate_invoice', methods=['GET', 'POST'])
def generate_invoice():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        items = request.form.getlist('item')
        unit_prices = request.form.getlist('unit_price')
        quantities = request.form.getlist('quantity')
        vat_percentages = request.form.getlist('vat_percentage')

        invoice = Invoice(user_id=user_id, date=datetime.now())
        db.session.add(invoice)
        db.session.flush()

        grand_total = 0  # Initialize grand total for the invoice

        for item, unit_price, quantity, vat_percentage in zip(items, unit_prices, quantities, vat_percentages):
            unit_price = float(unit_price)  # Convert to float
            quantity = int(quantity)  # Convert to integer
            vat_percentage = float(vat_percentage)  # Convert to float

            total = unit_price * quantity
            total += total * (vat_percentage / 100)  # Add the VAT to the total
            
            grand_total += total

            invoice_item = InvoiceItem(description=item, unit_price=unit_price, quantity=quantity, vat_percentage=vat_percentage, invoice_id=invoice.id)
            db.session.add(invoice_item)


        invoice.total = grand_total  # Save the adjusted grand total in the database
        db.session.commit()
        return redirect(url_for('view_invoice', invoice_id=invoice.id))

    users = User.query.all()
    return render_template('generate_invoice.html', users=users)




@app.route('/invoice/<int:invoice_id>')
def view_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    grand_total = 0
    for item in invoice.items:
        total = item.unit_price * item.quantity
        total += total * (item.vat_percentage / 100)
        tax=total*0.2
        grand_total += total-tax
    return render_template('invoice.html', invoice=invoice, grand_total=grand_total)


# from xhtml2pdf import pisa
# from flask import Response
# from io import BytesIO

@app.route('/download_invoice/<int:invoice_id>')
def download_invoice(invoice_id):
    # Fetch the invoice from the database
    invoice = Invoice.query.get(invoice_id)

    # Calculate the grand total
    grand_total = 0
    for item in invoice.items:
        total = item.unit_price * item.quantity
        total += total * (item.vat_percentage / 100)
        grand_total += total

    # Render the invoice as HTML
    html = render_template('invoice.html', invoice=invoice, grand_total=grand_total)

    # Convert the HTML to an image using Selenium
    image_path = html_to_image(html)

    # Serve the image as a response
    return Response(open(image_path, 'rb').read(), mimetype='image/png', headers={'Content-Disposition':'attachment;filename=invoice.png'})

def html_to_image(html_data):
    # Create a temporary HTML file
    html_file_path = '/tmp/invoice.html'
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(html_data)

    # Use Selenium to take a screenshot of the HTML page
    image_path = '/tmp/invoice.png'
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run Chrome in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1130')  # Set the window size to capture the entire page
    driver = webdriver.Chrome(options=options)
    driver.get(f'file://{html_file_path}')
    time.sleep(2)  # Wait for the page to load, adjust as needed

    driver.save_screenshot(image_path)
    driver.quit()

    # Clean up the temporary HTML file
    os.remove(html_file_path)

    return image_path

@app.route('/all_invoices')
def all_invoices():
    invoices = Invoice.query.all()
    return render_template('invoices.html', invoices=invoices)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)