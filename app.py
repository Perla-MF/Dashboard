import oracledb as cx_Oracle
import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from geopy.geocoders import Nominatim

# Configuración de conexión a la base de datos
host = "localhost"
port = "1521"
sid = "xe"
username = "PERLA_BD"
password = "5102."
dsn = cx_Oracle.makedsn(host, port, sid)

# Función para obtener los datos desde la base de datos
def obtener_datos():
    connection = cx_Oracle.connect(user=username, password=password, dsn=dsn)
    query = """
    SELECT GRADO,GÉNERO, NIVEL, AÑO, CATEGORÍA, LENGUA_INDÍGENA,EDAD,ESTADO_DE_NACIMIENTO
    FROM ALUMNOS_2008_2023
    """
    df = pd.read_sql(query, con=connection)
    connection.close()
    df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce')
    return df

df = obtener_datos()

# Coordenadas (latitud y longitud) para cada estado
geolocator = Nominatim(user_agent="geoapi")
def obtener_coordenadas(estado):
    location = geolocator.geocode(f"{estado}, México")
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

# Datos únicos para el mapa
def obtener_estados():
    connection = cx_Oracle.connect(user=username, password=password, dsn=dsn)
    query = "SELECT DISTINCT ESTADO_DE_NACIMIENTO FROM ALUMNOS_2008_2023"
    estados_df = pd.read_sql(query, con=connection)
    connection.close()
    estados_df["coordenadas"] = estados_df["ESTADO_DE_NACIMIENTO"].apply(obtener_coordenadas)
    estados_df[["lat", "lon"]] = pd.DataFrame(estados_df["coordenadas"].tolist(), index=estados_df.index)
    return estados_df.dropna(subset=["lat", "lon"])

estados_df = obtener_estados()

# Mapa con Plotly
def crear_mapa():
    fig = go.Figure(go.Scattermapbox(
        lat=estados_df["lat"],
        lon=estados_df["lon"],
        mode="markers",
        marker=go.scattermapbox.Marker(
            size=14,
            color="rgb(0, 123, 255)",
            opacity=0.8
        ),
        text=estados_df["ESTADO_DE_NACIMIENTO"],
        hoverinfo="text"
    ))

    # Configuración del mapa
    fig.update_layout(
        title="Distribución por Estado de Nacimiento",
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=23.6345, lon=-102.5528), 
            zoom=5
        ),
        showlegend=False
    )
    return fig

# Crear la pirámide poblacional
def crear_piramide_poblacional(df):
    df_agrupado = df.groupby(["EDAD", "GÉNERO"]).size().reset_index(name="COUNT")
    df_hombres = df_agrupado[df_agrupado["GÉNERO"] == "H"]
    df_mujeres = df_agrupado[df_agrupado["GÉNERO"] == "M"]
    edades = sorted(df_agrupado["EDAD"].unique())
    conteo_hombres = df_hombres.set_index("EDAD").reindex(edades, fill_value=0)["COUNT"]
    conteo_mujeres = df_mujeres.set_index("EDAD").reindex(edades, fill_value=0)["COUNT"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=edades,
        x=-conteo_hombres,
        name="Hombres",
        orientation="h",
        marker=dict(color="black")
    ))
    fig.add_trace(go.Bar(
        y=edades,
        x=conteo_mujeres,
        name="Mujeres",
        orientation="h",
        marker=dict(color="purple")
    ))
    fig.update_layout(
        title="Pirámide Poblacional",
        barmode="overlay",
        xaxis=dict(title="Población", tickvals=[-max(conteo_hombres), 0, max(conteo_mujeres)],
                   ticktext=[abs(max(conteo_hombres)), 0, max(conteo_mujeres)]),
        yaxis=dict(title="Edad"),
        template="plotly_white",
        legend=dict(x=0.9, y=1.1)
    )
    return fig

# Inicializar la aplicación Dash
app = Dash(__name__)

app.layout = html.Div([
    html.H1("ALUMNOS 2008-2023", style={"textAlign": "center"}),

    # Dropdown para filtrar la pirámide poblacional
    html.Label("Elija un rango de edad"),
    dcc.Dropdown(
        id="filtro-rango-edad",
        options=[{"label": f"{i}-{i+4}", "value": f"{i}-{i+4}"} for i in range(10, 76, 5)],
        value="0-4",
        clearable=False
    ),
    dcc.Graph(id="piramide-poblacional"),

    # Dropdown para filtrar por año en la gráfica de pastel
    html.Label("Elija un año"),
    dcc.Dropdown(
        id="filtro-año-pastel",
        options=[{"label": str(año), "value": año} for año in sorted(df["AÑO"].unique())],
        value=df["AÑO"].min(),
        clearable=False
    ),
    dcc.Graph(id="grafico-grado-genero"),

    # Heatmap (Relación entre Nivel y Año)
    dcc.Graph(
        id="grafico-heatmap",
        figure=px.density_heatmap(
            df,
            x="AÑO",
            y="NIVEL",
            title="Relación entre Nivel y Año",
            color_continuous_scale=px.colors.sequential.Viridis
        )
    ),

    # Filtro por año para la gráfica de Lenguas Indígenas
    html.Label("Elija un año: "),
    dcc.Dropdown(
        id="filtro-año-lenguas",
        options=[{"label": str(año), "value": año} for año in sorted(df["AÑO"].unique())],
        value=df["AÑO"].min(),
        clearable=False
    ),
    dcc.Graph(
        id="grafico-lengua-indigena",
        figure=px.bar(
            df.groupby("LENGUA_INDÍGENA").size().reset_index(name="COUNT"),
            x="LENGUA_INDÍGENA",
            y="COUNT",
            title="Lenguas Indígenas Más Habladas",
            color="LENGUA_INDÍGENA",
            color_discrete_sequence=px.colors.sequential.Viridis
    )
),

    # Filtro por año para la gráfica de Burbujas
    html.Label("Elija un año: "),
    dcc.Dropdown(
        id="filtro-año-burbujas",
        options=[{"label": str(año), "value": año} for año in sorted(df["AÑO"].unique())],
        value=df["AÑO"].min(),
        clearable=False
    ),
    dcc.Graph(
        id="grafico-nivel-categoria",
        figure=px.scatter(
            df.groupby(["NIVEL", "CATEGORÍA"]).size().reset_index(name="COUNT"),
            x="NIVEL",
            y="CATEGORÍA",
            size="COUNT",
            color="CATEGORÍA",
            title="Relación entre Nivel y Categoría",
            color_discrete_sequence=px.colors.sequential.Viridis,
            size_max=60
        )
    ),

    # Mapa interactivo (estados de nacimiento)
    dcc.Graph(
        id="mapa-estados",
        figure=crear_mapa()
    )
])

# Callbacks para filtros
@app.callback(
    Output("piramide-poblacional", "figure"),
    [Input("filtro-rango-edad", "value")]
)
def actualizar_piramide(rango_edad):
    edad_min, edad_max = map(int, rango_edad.split("-"))
    df_filtrado = df[(df["EDAD"] >= edad_min) & (df["EDAD"] <= edad_max)]
    return crear_piramide_poblacional(df_filtrado)

@app.callback(
    Output("grafico-grado-genero", "figure"),
    [Input("filtro-año-pastel", "value")]
)
def actualizar_pastel(año):
    df_filtrado = df[df["AÑO"] == año]
    return px.sunburst(
        df_filtrado,
        path=["GRADO", "GÉNERO"],
        title=f"Distribución de Alumnos por Grado y Género en {año}",
        color="GRADO",
        color_discrete_sequence=px.colors.sequential.Viridis
    )

@app.callback(
    Output("grafico-lengua-indigena", "figure"),
    [Input("filtro-año-lenguas", "value")]
)
def actualizar_lenguas(año):
    df_filtrado = df[df["AÑO"] == año]
    return px.bar(
        df_filtrado.groupby("LENGUA_INDÍGENA").size().reset_index(name="COUNT"),
        x="LENGUA_INDÍGENA",
        y="COUNT",
        title=f"Lenguas Indígenas en {año}",
        color="LENGUA_INDÍGENA"
    )

@app.callback(
    Output("grafico-nivel-categoria", "figure"),
    [Input("filtro-año-burbujas", "value")]
)
def actualizar_burbujas(año):
    df_filtrado = df[df["AÑO"] == año]
    return px.scatter(
        df_filtrado.groupby(["NIVEL", "CATEGORÍA"]).size().reset_index(name="COUNT"),
        x="NIVEL",
        y="CATEGORÍA",
        size="COUNT",
        title=f"Relación entre Nivel y Categoría en {año}",
        size_max=60
    )

if __name__ == "__main__":
    app.run_server(debug=True)
