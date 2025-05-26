from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired, NumberRange

class VenderLaptopForm(FlaskForm):
    nombre = StringField('Nombre del Producto', validators=[DataRequired()])
    precio = FloatField('Precio (USD)', validators=[DataRequired(), NumberRange(min=0.01)])
    descripcion = TextAreaField('Descripción', validators=[DataRequired()])
    imagen = FileField('Imagen del Producto')
    cancel = SubmitField('Cancelar')
    submit = SubmitField('Publicar Producto')