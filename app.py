import os
import sys
import re
import uuid
import subprocess
from flask import Flask, render_template, session, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Crear la APP
app = Flask(__name__)

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from config import MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB, SECRET_KEY, TITLE, PREFIX

# Conexión a la base de datos 'mydb'
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TITLE'] = 'My pharmacokinetic'
app.config['SECRET_KEY'] = 'my_secret_key'

db = SQLAlchemy(app)

# User log in 
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# Register route: 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email =request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            return "Your email has been registered"
        
        new_user = User(email=email, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html')

# Log in route: 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            return "Incorrect login"
    return render_template('login.html')

# Log out route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# Página de inicio
@app.route('/')
def index():   
    return render_template('index.html') 

# LISTAR DRUGS
@app.route('/drugs')
@login_required
def listar_drugs():
    result = db.session.execute(text("SELECT * FROM drugs"))
    columnas = result.keys()
    # Obtenemos todas las filas
    datos = result.fetchall()
    return render_template('drug.html', columnas=columnas, filas=datos, title="Drug List")

@app.route('/buscar_drugs', methods=['GET','POST'])
def buscar_drug():
    termino = request.form.get('nombre_droga')
    query = text("SELECT * FROM drugs WHERE drug_name LIKE :nombre")
  
    result = db.session.execute(query, {"nombre": f"%{termino}%"})  
    columnas = result.keys()
    datos = [dict(zip(columnas, fila)) for fila in result.fetchall()]
    
    return render_template('drug.html', columnas=columnas, filas=datos, title=f"Resultados para: {termino}")

# LISTAR VARIANTES - GENES
@app.route('/variants')
@login_required
def listar_variants():
    result = db.session.execute(text("SELECT variant_name FROM variants"))
    datos = result.fetchall()
    return render_template('variants.html', filas=datos, title="Variant List")

# DETALLES DE UNA VARIANTE 
@app.route('/variants/<string:nombre_variante>')
@login_required
def mostrar_detalles_variant(nombre_variante):
    res_variant = db.session.execute(
        text("SELECT * FROM variants WHERE variant_name = :nombre"), 
        {"nombre": nombre_variante})
    info_variante = res_variant.fetchone()

    if not info_variante:
        return "Variante no encontrada", 404

    # Buscamos los FÁRMACOS asociados a una variante específica
    query_drugs = text("""
        SELECT d.drug_name 
        FROM drugs d
        JOIN variants_has_drugs vhd ON d.drug_name = vhd.drugs_drug_name
        WHERE vhd.variants_variant_name = :nombre
    """)
    res_drugs = db.session.execute(query_drugs, {"nombre": nombre_variante})
    listado_farmacos = res_drugs.fetchall()

    return render_template(
        'detalles_variants.html', variante=info_variante, farmacos=listado_farmacos, title=f"Detalles de {nombre_variante}")

# Busqueda farmaco - variantes asociadas 
@app.route('/drugs/<string:nombre_farmaco>')
def mostrar_detalles_drug(nombre_farmaco):
    res_drug = db.session.execute(
        text("SELECT * FROM drugs WHERE drug_name = :nombre"), 
        {"nombre": nombre_farmaco}
    )
    info_droga = res_drug.fetchone()

    if not info_droga:
        return "Fármaco no encontrado", 404

    # Buscar las variantes asociadas
    query_variantes = text("""
        SELECT v.* FROM variants v
        JOIN variants_has_drugs dv ON v.variant_name = dv.variants_variant_name
        WHERE dv.drugs_drug_name = :nombre
    """)
    res_variantes = db.session.execute(query_variantes, {"nombre": nombre_farmaco})
    listado_variantes = res_variantes.fetchall()

    return render_template(
        'detalles_drug.html', 
        droga=info_droga, 
        variantes=listado_variantes,
        title=f"Detalles de {nombre_farmaco}"
    )

# Buscar Farmaco y variante a la vez
@app.route('/search')
@login_required     
def search():
    drug_query = request.args.get("drug", "").strip()
    variant_query = request.args.get("variant", "").strip()
    evidencias_raw = db.session.execute(text("SELECT evidence_category, evidence_description FROM evidence_category")).fetchall()
    glosario_evidencia = {row[0]: row[1] for row in evidencias_raw}

    sql = """
        SELECT dv.id_annotation,dv.drugs_drug_name, dv.variants_variant_name, dv.phenotype_category_phenotype_category, dv.illness_illness_name, dv.evidence_category_evidence_category,dv.URL_web
        FROM variants_has_drugs dv
        JOIN variants v ON dv.variants_variant_name = v.variant_name
        WHERE 1=1
    """
    
    params = {}
    
    if drug_query:
        sql += " AND dv.drugs_drug_name LIKE :drug"
        params["drug"] = f"%{drug_query}%"
    
    if variant_query:
        sql += " AND dv.variants_variant_name LIKE :variant"
        params["variant"] = f"%{variant_query}%"
    
    result = db.session.execute(text(sql), params)
    columnas = result.keys()
    results = [dict(zip(columnas, fila)) for fila in result.fetchall()]

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        return jsonify(results)
    
    return render_template("results.html", results=results, drug=drug_query, variant=variant_query, glosario=glosario_evidencia)


# Buscar Evidence-Category
@app.route("/evidence/<string:category_name>")
def detalle_evidencia(category_name):
    query = text("""
        SELECT evidence_category, evidence_description 
        FROM evidence_category 
        WHERE evidence_category = :cat
    """)
    result = db.session.execute(query, {"cat": category_name})
    info_evidencia = result.fetchone()

    if not info_evidencia:
        return "Categoría de evidencia no encontrada", 404

    return render_template("detalles_evidencia.html", evidencia=info_evidencia)


# Relacion id-annotation con id-evidence
@app.route("/evidencia_articulos/<int:id_annotation>")
@login_required
def evidencia_articulos(id_annotation):
    sql = """
        SELECT id_evidence, summary_text, PMID 
        FROM PMID 
        WHERE variants_has_drugs_id_annotation = :id_annot
    """
    
    result = db.session.execute(text(sql), {"id_annot": id_annotation})
    columnas = result.keys()
    articulos = [dict(zip(columnas, fila)) for fila in result.fetchall()]

    info_extra = db.session.execute(text("""
        SELECT drugs_drug_name, variants_variant_name 
        FROM variants_has_drugs 
        WHERE id_annotation = :id_annot
    """), {"id_annot": id_annotation}).fetchone()

    if not articulos:
        pass

    return render_template("evidencia_articulos.html", 
                           articulos=articulos, 
                           info=info_extra,
                           id_annot=id_annotation)

hostedApp = Flask(__name__)
hostedApp.wsgi_app = DispatcherMiddleware(NotFound(), {f"{PREFIX}": app.wsgi_app})

if __name__ == '__main__':
    hostedApp.run(debug=True, port=5000)
