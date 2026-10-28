#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, sqlite3, random, string, datetime, uuid, csv, io, os, urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DBS = {
    "loja_db": DATA / "loja.db",
    "escola_db": DATA / "escola.db",
    "dataforge": DATA / "dataforge.db",
}

SCHEMAS = {
    "loja_db": [
        """CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE
        )""",
        """CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            preco REAL NOT NULL CHECK(preco >= 0), stock INTEGER NOT NULL DEFAULT 0,
            categoria_id INTEGER NOT NULL REFERENCES categorias(id),
            descricao TEXT NOT NULL DEFAULT '', origem_dados TEXT NOT NULL DEFAULT 'sintetico'
        )""",
        """CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, telefone TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            data_encomenda TEXT NOT NULL, estado TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS itens_encomenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            encomenda_id INTEGER NOT NULL REFERENCES encomendas(id),
            produto_id INTEGER NOT NULL REFERENCES produtos(id),
            quantidade INTEGER NOT NULL CHECK(quantidade > 0), preco_unitario REAL NOT NULL
        )"""
    ],
    "escola_db": [
        """CREATE TABLE IF NOT EXISTS professores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE
        )""",
        """CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE,
            professor_id INTEGER NOT NULL REFERENCES professores(id)
        )""",
        """CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE,
            professor_id INTEGER NOT NULL REFERENCES professores(id)
        )""",
        """CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            data_nascimento TEXT NOT NULL, email TEXT NOT NULL UNIQUE
        )""",
        """CREATE TABLE IF NOT EXISTS matriculas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER NOT NULL REFERENCES alunos(id),
            turma_id INTEGER NOT NULL REFERENCES turmas(id), ano_lectivo TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, matricula_id INTEGER NOT NULL REFERENCES matriculas(id),
            disciplina_id INTEGER NOT NULL REFERENCES disciplinas(id),
            nota REAL NOT NULL CHECK(nota >= 0 AND nota <= 20)
        )"""
    ]
}

def connect(key):
    if key not in DBS:
        raise ValueError("Base de dados desconhecida.")
    con = sqlite3.connect(DBS[key], timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    for key in ("loja_db", "escola_db"):
        with connect(key) as con:
            for sql in SCHEMAS[key]:
                con.execute(sql)
    # Migração segura para bases criadas por versões anteriores do DataForge.
    with connect("loja_db") as con:
        columns = [r["name"] for r in con.execute('PRAGMA table_info("produtos")')]
        if "descricao" not in columns:
            con.execute("ALTER TABLE produtos ADD COLUMN descricao TEXT NOT NULL DEFAULT ''")
        if "origem_dados" not in columns:
            con.execute("ALTER TABLE produtos ADD COLUMN origem_dados TEXT NOT NULL DEFAULT 'sintetico'")
    with connect("dataforge") as con:
        con.execute("""CREATE TABLE IF NOT EXISTS execucoes (
            id TEXT PRIMARY KEY, modulo TEXT NOT NULL, quantidade INTEGER NOT NULL,
            origem TEXT NOT NULL, estado TEXT NOT NULL, total_registos INTEGER NOT NULL,
            detalhes TEXT NOT NULL, criada_em TEXT NOT NULL
        )""")

def names():
    return ["Ana", "Mateus", "João", "Marta", "Paulo", "Lúcia", "Carlos", "Rosa", "Dário", "Sónia", "Manuel", "Eva"]
def person():
    return random.choice(names()) + " " + random.choice(["Domingos", "Silva", "Manuel", "Pedro", "Afonso", "Neto", "João"])
def email(prefix):
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.test"
def table_names(con):
    return [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

def inspect_database(module):
    with connect(module) as con:
        result = []
        for table in table_names(con):
            cols = [dict(r) for r in con.execute(f'PRAGMA table_info("{table}")')]
            fks = [dict(r) for r in con.execute(f'PRAGMA foreign_key_list("{table}")')]
            count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            result.append({"name": table, "columns": cols, "foreign_keys": fks, "count": count})
        fk_errors = [dict(r) for r in con.execute("PRAGMA foreign_key_check")]
        return {"module": module, "database_file": DBS[module].name, "tables": result, "foreign_key_errors": fk_errors}

def fetch_online_products(qty):
    """Obtém produtos de uma API pública (DummyJSON)."""
    url = f"https://dummyjson.com/products?limit={min(qty, 194)}&skip=0&select=title,description,price,stock,category"
    request = urllib.request.Request(url, headers={"User-Agent": "DataForge/1.0 (academic data seeding)", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            if response.status != 200:
                raise RuntimeError(f"A fonte online respondeu com HTTP {response.status}.")
            payload = json.loads(response.read(3_000_000).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Não foi possível obter dados da Internet. Verifica a ligação e tenta novamente. Detalhe: " + str(exc)) from exc
    products = payload.get("products", [])
    cleaned = []
    for item in products[:qty]:
        try:
            cleaned.append({
                "nome": str(item.get("title") or "Produto online")[:180],
                "descricao": str(item.get("description") or "")[:1000],
                "preco": max(0, float(item.get("price", 0))),
                "stock": max(0, int(item.get("stock", 0))),
                "categoria": str(item.get("category") or "Outros")[:80],
            })
        except (TypeError, ValueError):
            continue
    return cleaned

def seed_shop(con, qty, origin="sintetico", online_products=None):
    category_names = ["Informática", "Casa", "Moda", "Acessórios", "Telemóveis", "Áudio", "Desporto", "Outros"]
    online_products = online_products or []
    for product in online_products:
        if product["categoria"] not in category_names:
            category_names.append(product["categoria"])
    for name in category_names:
        con.execute("INSERT OR IGNORE INTO categorias(nome) VALUES(?)", (name,))
    category_ids = {r["nome"]: r["id"] for r in con.execute("SELECT id,nome FROM categorias")}
    existing_products = con.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
    imported = 0
    for product in online_products[:qty]:
        con.execute("INSERT INTO produtos(nome,preco,stock,categoria_id,descricao,origem_dados) VALUES(?,?,?,?,?,?)",
                    (product["nome"], product["preco"], product["stock"], category_ids[product["categoria"]], product["descricao"], "internet"))
        imported += 1
    synthetic_qty = qty - imported if origin == "misto" else (0 if origin == "internet" else qty)
    for i in range(synthetic_qty):
        category = random.choice(category_names)
        con.execute("INSERT INTO produtos(nome, preco, stock, categoria_id, descricao, origem_dados) VALUES(?,?,?,?,?,?)",
                    (f"Produto sintético {existing_products+i+1:04d}", round(random.uniform(1500, 85000), 2), random.randint(0, 150), category_ids[category], "Produto gerado pelo DataForge.", "sintetico"))
    # Clientes e encomendas são sempre sintéticos; não importamos dados pessoais da Internet.
    client_ids = []
    for _ in range(qty):
        cur = con.execute("INSERT INTO clientes(nome,email,telefone) VALUES(?,?,?)",
                          (person(), email("cliente"), f"9{random.randint(10000000,99999999)}"))
        client_ids.append(cur.lastrowid)
    product_ids = [r[0] for r in con.execute("SELECT id FROM produtos")]
    for _ in range(qty):
        cur = con.execute("INSERT INTO encomendas(cliente_id,data_encomenda,estado) VALUES(?,?,?)",
                          (random.choice(client_ids), datetime.date.today().isoformat(), random.choice(["Pendente","Paga","Enviada","Entregue"])))
        order_id = cur.lastrowid
        if product_ids:
            for product_id in random.sample(product_ids, k=min(random.randint(1, 3), len(product_ids))):
                price = con.execute("SELECT preco FROM produtos WHERE id=?", (product_id,)).fetchone()[0]
                con.execute("INSERT INTO itens_encomenda(encomenda_id,produto_id,quantidade,preco_unitario) VALUES(?,?,?,?)",
                            (order_id, product_id, random.randint(1, 4), price))
    return imported, synthetic_qty

def seed_school(con, qty):
    teachers = [r[0] for r in con.execute("SELECT id FROM professores")]
    if not teachers:
        for i in range(8):
            con.execute("INSERT INTO professores(nome,email) VALUES(?,?)", (person(), email("professor")))
        teachers = [r[0] for r in con.execute("SELECT id FROM professores")]
    classes = [r[0] for r in con.execute("SELECT id FROM turmas")]
    if not classes:
        for i in range(6):
            con.execute("INSERT INTO turmas(nome,professor_id) VALUES(?,?)", (f"Turma {i+1:02d}", random.choice(teachers)))
        classes = [r[0] for r in con.execute("SELECT id FROM turmas")]
    subjects = [r[0] for r in con.execute("SELECT id FROM disciplinas")]
    if not subjects:
        for name in ["Matemática", "Português", "Informática", "Física", "Química", "Inglês"]:
            con.execute("INSERT INTO disciplinas(nome,professor_id) VALUES(?,?)", (name, random.choice(teachers)))
        subjects = [r[0] for r in con.execute("SELECT id FROM disciplinas")]
    student_ids = []
    for _ in range(qty):
        cur = con.execute("INSERT INTO alunos(nome,data_nascimento,email) VALUES(?,?,?)",
                          (person(), f"{random.randint(2002,2010)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}", email("aluno")))
        student_ids.append(cur.lastrowid)
    for student_id in student_ids:
        cur = con.execute("INSERT INTO matriculas(aluno_id,turma_id,ano_lectivo) VALUES(?,?,?)",
                          (student_id, random.choice(classes), "2026/2027"))
        enrolment_id = cur.lastrowid
        for subject_id in subjects:
            con.execute("INSERT INTO notas(matricula_id,disciplina_id,nota) VALUES(?,?,?)",
                        (enrolment_id, subject_id, round(random.uniform(0, 20), 1)))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def send_json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_json(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path, q = parsed.path, parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                if path == "/api/health":
                    return self.send_json(200, {"status":"ok","service":"dataforge-api","database":"SQLite"})
                if path == "/api/modules":
                    return self.send_json(200, {"modules":[{"id":"loja_db","name":"Loja Online"},{"id":"escola_db","name":"Sistema Escolar"}]})
                if path == "/api/tables":
                    module = q.get("module", ["loja_db"])[0]
                    return self.send_json(200, inspect_database(module))
                if path == "/api/rows":
                    module = q.get("module", ["loja_db"])[0]
                    table = q.get("table", [""])[0]
                    search = q.get("search", [""])[0][:100]
                    page = max(1, int(q.get("page", ["1"])[0]))
                    if not table or table not in inspect_database(module)["tables"] and table not in [t["name"] for t in inspect_database(module)["tables"]]:
                        return self.send_json(400, {"error":"Tabela inválida."})
                    with connect(module) as con:
                        cols = [r["name"] for r in con.execute(f'PRAGMA table_info("{table}")')]
                        where, params = "", []
                        if search:
                            where = " WHERE " + " OR ".join(f'CAST("{c}" AS TEXT) LIKE ?' for c in cols)
                            params = [f"%{search}%"] * len(cols)
                        total = con.execute(f'SELECT COUNT(*) FROM "{table}"{where}', params).fetchone()[0]
                        rows = [dict(r) for r in con.execute(f'SELECT * FROM "{table}"{where} ORDER BY 1 DESC LIMIT 50 OFFSET ?', (*params, (page-1)*50))]
                    return self.send_json(200, {"table":table,"columns":cols,"rows":rows,"total":total,"page":page,"page_size":50})
                if path == "/api/reports":
                    with connect("dataforge") as con:
                        rows = [dict(r) for r in con.execute("SELECT * FROM execucoes ORDER BY criada_em DESC LIMIT 100")]
                    for row in rows:
                        row["detalhes"] = json.loads(row["detalhes"])
                    return self.send_json(200, {"reports":rows})
                return self.send_json(404, {"error":"Endpoint não encontrado."})
            except (ValueError, KeyError) as e:
                return self.send_json(400, {"error":str(e)})
            except Exception as e:
                return self.send_json(500, {"error":"Erro interno: "+str(e)})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/generate", "/api/clear"):
            return self.send_json(404, {"error":"Endpoint não encontrado."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            module = payload.get("module", "loja_db")
            if path == "/api/clear":
                if module not in ("loja_db", "escola_db"):
                    return self.send_json(400, {"error":"Selecciona um módulo válido."})
                if payload.get("confirm") != module:
                    return self.send_json(400, {"error":"Confirma explicitamente o módulo a limpar."})
                with connect(module) as con:
                    before = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in table_names(con)}
                    # Apagar primeiro as tabelas-filhas para respeitar as chaves estrangeiras.
                    order = (["itens_encomenda", "encomendas", "produtos", "clientes", "categorias"] if module == "loja_db"
                             else ["notas", "matriculas", "alunos", "turmas", "disciplinas", "professores"])
                    for table in order:
                        con.execute(f'DELETE FROM "{table}"')
                    for table in order:
                        con.execute(f'DELETE FROM sqlite_sequence WHERE name=?', (table,))
                    fk_errors = [dict(r) for r in con.execute("PRAGMA foreign_key_check")]
                    if fk_errors:
                        raise RuntimeError("A limpeza detectou problemas de integridade; operação cancelada.")
                deleted = sum(before.values())
                started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
                report_id = str(uuid.uuid4())
                details = {"database_file": DBS[module].name, "deleted_counts": before, "foreign_key_errors": 0, "message":"Módulo limpo; histórico de relatórios preservado."}
                with connect("dataforge") as con:
                    con.execute("INSERT INTO execucoes VALUES(?,?,?,?,?,?,?,?)", (report_id,module,0,"limpeza","concluída",deleted,json.dumps(details,ensure_ascii=False),started))
                return self.send_json(200, {"status":"limpo","module":module,"deleted_records":deleted,"deleted_counts":before,"database_file":DBS[module].name,"reports_preserved":True})

            qty = int(payload.get("quantity", 100))
            origin = payload.get("origin", "sintetico")
            if module not in ("loja_db", "escola_db"):
                return self.send_json(400, {"error":"Selecciona uma base de dados válida."})
            if not 1 <= qty <= 5000:
                return self.send_json(400, {"error":"A quantidade deve estar entre 1 e 5000."})
            if origin not in ("sintetico", "internet", "misto"):
                return self.send_json(400, {"error":"Origem inválida."})
            if module == "escola_db" and origin != "sintetico":
                return self.send_json(400, {"error":"A origem Internet/Misto está disponível para produtos da Loja Online. No Sistema Escolar, usa dados sintéticos para não importar dados pessoais."})
            online_products = fetch_online_products(qty) if module == "loja_db" and origin in ("internet", "misto") else []
            if origin == "internet" and not online_products:
                return self.send_json(502, {"error":"A fonte online não devolveu produtos para importar."})
            started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            with connect(module) as con:
                before = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in table_names(con)}
                imported_online = 0
                generated_synthetic = 0
                if module == "loja_db":
                    imported_online, generated_synthetic = seed_shop(con, qty, origin, online_products)
                else:
                    seed_school(con, qty)
                fk_errors = [dict(r) for r in con.execute("PRAGMA foreign_key_check")]
                if fk_errors:
                    raise RuntimeError("A validação encontrou referências inválidas; a transacção foi cancelada.")
                after = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in table_names(con)}
                counts = {t: after[t]-before.get(t,0) for t in after}
                total = sum(counts.values())
            report_id = str(uuid.uuid4())
            details = {"database_file": DBS[module].name, "table_counts": counts, "foreign_key_errors": len(fk_errors), "imported_online": imported_online, "generated_synthetic_products": generated_synthetic, "source": "DummyJSON API" if imported_online else "DataForge", "message":"Execução concluída; chaves estrangeiras verificadas."}
            with connect("dataforge") as con:
                con.execute("INSERT INTO execucoes VALUES(?,?,?,?,?,?,?,?)",
                            (report_id,module,qty,origin,"concluída",total,json.dumps(details,ensure_ascii=False),started))
            return self.send_json(201, {"id":report_id,"module":module,"quantity":qty,"origin":origin,"status":"concluída","total_records_inserted":total,"table_counts":counts,"foreign_key_errors":len(fk_errors),"created_at":started,"database_file":DBS[module].name,"imported_online":imported_online,"generated_synthetic_products":generated_synthetic,"source":"DummyJSON API" if imported_online else "DataForge"})
        except Exception as e:
            return self.send_json(500, {"error":str(e)})

def main():
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("DataForge API + SQLite disponível em http://localhost:8000")
    print(f"Ficheiros SQLite: {DATA}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
