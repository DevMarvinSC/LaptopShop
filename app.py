from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Laptop
from werkzeug.security import generate_password_hash, check_password_hash
from forms import VenderLaptopForm
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
db.init_app(app)

# Crear tablas (ejecutar solo una vez)
with app.app_context():
    db.create_all()


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Ruta para redirigir si no está autenticado

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403


app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# -------------------------------- Rutas -------------------------------
@app.route('/')
def index():
    search_query = request.args.get('search', '').strip()  # Obtener parámetro de búsqueda

    laptops_query = Laptop.query
    
    if search_query:
        # Búsqueda en nombre Y descripción (insensible a mayúsculas)
        laptops = laptops_query.filter(
            db.or_(
                Laptop.name.ilike(f'%{search_query}%'),
                Laptop.description.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        laptops = False
    laptopsSiempre = laptops_query.all()
    
    return render_template('index.html', laptops=laptops, laptopsSiempre= laptopsSiempre, search_query=search_query)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)  # <-- Iniciar sesión
            flash('¡Bienvenido!', 'success')
            return redirect(url_for('dashboard'))  # Redirigir al dashboard
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        telefono = request.form['telefono']
        password = request.form['password']
        
        # Validar si el email o username ya existen
        user_email = User.query.filter_by(email=email).first()
        user_username = User.query.filter_by(username=username).first()
        
        if user_email:
            flash('Este email ya está registrado', 'danger')
            return redirect(url_for('register'))
        if user_username:
            flash('Este nombre de usuario ya existe', 'danger')
            return redirect(url_for('register'))
        
        # Crear usuario si no existe
        user = User(username=username, email=email, telefono=telefono)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registro exitoso. ¡Ahora puedes iniciar sesión!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()  # <-- Cerrar sesión
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required  # <-- Requiere autenticación
def dashboard():
    return render_template('dashboard.html')

@app.route('/vender', methods=['GET', 'POST'])
@login_required
def vender():
    form = VenderLaptopForm()
    if form.validate_on_submit():
        imagen = form.imagen.data
        if imagen and allowed_file(imagen.filename):
            # Generar nombre único
            extension = imagen.filename.rsplit('.', 1)[1].lower()
            nombre_unico = f"{uuid.uuid4().hex}.{extension}"
            filename = secure_filename(nombre_unico)
            
            # Guardar imagen
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_url = url_for('static', filename=f'uploads/{filename}')

        # Crear nuevo producto
        nueva_laptop = Laptop(
            name=form.nombre.data,
            price=form.precio.data,
            description=form.descripcion.data,
            image_url=imagen_url,
            user_id=current_user.id  # Asignar al usuario actual
        )
        db.session.add(nueva_laptop)
        db.session.commit()

        flash('¡Producto publicado exitosamente!', 'success')
        return redirect(url_for('dashboard'))
        

    return render_template('vender.html', form=form)

@app.route('/mis-productos')
@login_required
def mis_productos():
    # Obtener solo las laptops del usuario actual
    laptops = Laptop.query.filter_by(user_id=current_user.id).all()
    return render_template('mis_productos.html', laptops=laptops)

@app.route('/eliminar-producto/<int:id>', methods=['POST'])
@login_required
def eliminar_producto(id):
    laptop = Laptop.query.get_or_404(id)
    # Verificar que el producto pertenece al usuario
    if laptop.user_id != current_user.id:
        abort(403)  # Prohibido si no es el dueño
    
    # Eliminar imagen del sistema de archivos (opcional)
    if laptop.image_url:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], laptop.image_url.split('/')[-1]))
        except:
            pass
    
    db.session.delete(laptop)
    db.session.commit()
    flash('Producto eliminado', 'success')
    return redirect(url_for('mis_productos'))

@app.route('/editar-producto/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    laptop = Laptop.query.get_or_404(id)
    if laptop.user_id != current_user.id:
        abort(403)  # Solo el dueño puede editar

    # Precargar el formulario con los datos existentes
    form = VenderLaptopForm(
        nombre=laptop.name,
        precio=laptop.price,
        descripcion=laptop.description,
        # La imagen no se precarga (se maneja diferente)
    )

    if form.validate_on_submit():
        # Actualizar los datos (excepto la imagen si no se cambia)
        laptop.name = form.nombre.data
        laptop.price = form.precio.data
        laptop.description = form.descripcion.data
        
        # Manejo de imagen (opcional: solo si se sube una nueva)
        if form.imagen.data:
            imagen = form.imagen.data
            # Generar nombre único
            extension = imagen.filename.rsplit('.', 1)[1].lower()
            nombre_unico = f"{uuid.uuid4().hex}.{extension}"
            filename = secure_filename(nombre_unico)
                
                # Guardar imagen
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_url = url_for('static', filename=f'uploads/{filename}')
            laptop.image_url = imagen_url

        db.session.commit()
        flash('¡Producto actualizado!', 'success')
        return redirect(url_for('mis_productos'))

    return render_template('editar_producto.html', form=form, laptop=laptop)
# -------------------------- Detalles del producto
@app.route('/producto/<int:id>')
def detalle_producto(id):
    laptop = Laptop.query.get_or_404(id)  # Si no existe, muestra error 404
    return render_template('detalle_producto.html', laptop=laptop)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')