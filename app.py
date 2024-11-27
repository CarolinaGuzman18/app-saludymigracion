import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
import folium
from streamlit_folium import folium_static
from streamlit_folium import st_folium
from branca.colormap import linear


# ----- Fuentes de datos -----

# URL del archivo de datos. 
URL_DATOS_CENTROS = 'datos_completos.csv'

# URL del archivo de cantones. 
URL_DATOS_CANTONES = 'cantones_centros_salud.gpkg'


# Función para cargar los datos y almacenarlos en caché 
# para mejorar el rendimiento
@st.cache_data
def cargar_datos_centros():
    # Leer el archivo CSV y cargarlo en un DataFrame de pandas
    datos = pd.read_csv(URL_DATOS_CENTROS)
    return datos

# Función para cargar los datos geoespaciales de cantones
@st.cache_data
def cargar_datos_cantones():
    cantones  = gpd.read_file(URL_DATOS_CANTONES)
    return cantones

#Título de la aplicación 
st.title("Acceso a la salud de las personas migrantes en tránsito por Costa Rica")

# ----- Carga de datos -----

# Mostrar un mensaje mientras se cargan los datos de Centros de Salud
estado_carga_centros = st.text('Cargando datos de Centros de Salud...')
# Cargar los datos
datos = cargar_datos_centros()
# Actualizar el mensaje una vez que los datos han sido cargados
estado_carga_centros.text('Realizado por Carolina Guzmán Herrera')

# Cargar datos geoespaciales de cantones
estado_carga_cantones = st.text('Cargando datos de cantones...')
cantones = cargar_datos_cantones()
estado_carga_cantones.text('')

# ----- Preparación de datos -----

# Columnas relevantes del conjunto de datos
columnas = [
    'name', 
    'operator', 
    'PROVINCIA', 
    'CANTÓN',
    'ruta'
]

datos = datos[columnas]

# Nombres de las columnas en español
columnas_espaniol = {
    'name': 'Nombre',
    'operator': 'Operador',
    'PROVINCIA': 'Provincia',
    'CANTÓN': 'Cantón',
    'ruta': 'Establecimiento'
}
datos = datos.rename(columns=columnas_espaniol)

# ----- Lista de selección en la barra lateral -----

# Obtener la lista de cantones únicos
lista_cantones = datos['Cantón'].unique().tolist()
lista_cantones.sort()

# Añadir la opción "Todos" al inicio de la lista
opciones_cantones = ['Todos'] + lista_cantones

# Crear el selectbox en la barra lateral
canton_seleccionado = st.sidebar.selectbox(
    'Selecciona un canton',
    opciones_cantones
)


# ----- Filtrar datos según la selección -----

if canton_seleccionado != 'Todos':
    # Filtrar los datos para el cantón seleccionado
    datos_filtrados = datos[datos['Cantón'] == canton_seleccionado]

   
else:
    # No aplicar filtro
    datos_filtrados = datos.copy()


# ----- Tabla de centros de salud totales por cantón y provincia

# Mostrar la tabla
st.subheader('Centros de salud cercanos a la ruta migratoria')
st.dataframe(datos_filtrados, hide_index=True)


# ----- Gráfico de centros de salud cercanos a la ruta migratoria por cantón -----

if canton_seleccionado != 'Todos':
    # Filtrar los datos para el cantón seleccionado
    centros_totales_por_canton = (
        datos[datos['Cantón'] == canton_seleccionado]
        .groupby(['Provincia', 'Cantón'])['Establecimiento']
        .sum()
        .reset_index()
    )
else:
    # Usar todos los datos si no se selecciona un cantón específico
    centros_totales_por_canton = (
        datos
        .groupby(['Provincia', 'Cantón'])['Establecimiento']
        .sum()
        .reset_index()
    )

# Ordenar las provincias por centro de salud total descendente
centros_provincia = (
    centros_totales_por_canton
    .groupby('Provincia')['Establecimiento']
    .sum()
    .sort_values(ascending=False)
    .index
)

# Asignar el orden de las categorías en el eje X
centros_totales_por_canton['Provincia'] = pd.Categorical(
    centros_totales_por_canton['Provincia'],
    categories=centros_provincia,
    ordered=True
)

# Crear el gráfico de barras
fig = px.bar(
    centros_totales_por_canton,
    x='Provincia',
    y='Establecimiento',
    color='Cantón',
    labels={
        'Provincia': 'Provincia',
        'Cantón': 'Cantón',
        'Establecimiento': 'Centros de salud'
    },
    category_orders={'Provincia': centros_provincia},  # Aplicar el orden de las provincias
    width=1000,
    height=600
)

# Actualizar el formato del eje y para evitar notación científica
fig.update_yaxes(tickformat=",d")

# Atributos globales de la figura
fig.update_layout(
    xaxis_title=dict(font=dict(size=16)),
    yaxis_title=dict(font=dict(size=16)),
    legend_title=dict(
        text='Cantón',
        font=dict(size=16)
    ),
    legend=dict(
        title_font_size=16,
        font_size=14,
        x=1.05,
        y=1
    )
)

# Mostrar el gráfico
st.subheader('Distribución por cantón y provincia de centros de salud cercanos a la ruta migratoria')
st.plotly_chart(fig)


# ----- Mapa de coropletas con folium -----

# Agrupar los centros de salud por cantón
if canton_seleccionado != 'Todos':
    centros_totales_por_canton = (
        datos_filtrados
        .groupby('Cantón')['Establecimiento']
        .max()
        .reset_index()
    )
else:
    centros_totales_por_canton = (
        datos
        .groupby('Cantón')['Establecimiento']
        .max()
        .reset_index()
    )

# Unir los datos de centros con el GeoDataFrame de cantones
cantones_merged = cantones.merge(
    centros_totales_por_canton,
    how='left',
    left_on='CANTÓN',
    right_on='Cantón'
)

# Reemplazar valores nulos por cero en 'Establecimientos'
cantones_merged['Centros de salud'] = cantones_merged['Centros de salud'].fillna(0)


# Establecer las coordenadas del centro de Costa Rica
coordenadas = [9.7489, -83.7534]  
zoom_level = 8  



# Crear el mapa base
if canton_seleccionado != 'Todos':
    # Filtrar el GeoDataFrame para obtener la geometría del cantón seleccionado
    canton_geom = cantones[cantones['CANTÓN'] == datos_filtrados['Cantón'].iloc[0]]
    
    if not canton_geom.empty:
        # Obtener el centroide de la geometría del cantón seleccionado
        centroid = canton_geom.geometry.centroid.iloc[0]
        coordenadas = [centroid.y, centroid.x]
        zoom_level = 10  # Zoom más cercano para un cantón
    else:
        # Si no se encuentra el cantón, usar las coordenadas de Costa Rica
        coordenadas = [9.7489, -83.7534]  # Coordenadas de Costa Rica
        zoom_level = 7

    # Filtrar `cantones_merged` para mostrar solo el cantón seleccionado
    cantones_filtrados = cantones_merged[cantones_merged['CANTÓN'] == datos_filtrados['Cantón'].iloc[0]]
else:
    # Centrar el mapa en Costa Rica si no hay cantón seleccionado
    coordenadas = [9.7489, -83.7534]  # Coordenadas aproximadas de Costa Rica
    zoom_level = 7  # Nivel de zoom adecuado para visualizar el país

    # Usar todos los cantones en el mapa
    cantones_filtrados = cantones_merged

# Crear el mapa base
mapa = folium.Map(location=coordenadas, zoom_start=zoom_level)

# Crear una paleta de colores
from branca.colormap import linear
paleta_colores = linear.YlOrRd_09.scale(
    cantones_filtrados['Centros de salud'].min(),
    cantones_filtrados['Centros de salud'].max()
)

# Añadir los polígonos al mapa (solo el cantón seleccionado si aplica)
folium.GeoJson(
    cantones_filtrados,
    name='Centros de salud por cantón',
    style_function=lambda feature: {
        'fillColor': paleta_colores(feature['properties']['Centros de salud']),
        'color': 'black',
        'weight': 0.5,
        'fillOpacity': 0.7,
    },
    highlight_function=lambda feature: {
        'weight': 3,
        'color': 'black',
        'fillOpacity': 0.9,
    },
    tooltip=folium.features.GeoJsonTooltip(
        fields=['CANTÓN', 'Centros de salud'],
        aliases=['Cantón: ', 'Centros de salud: '],
        localize=True
    )
).add_to(mapa)

# Añadir la leyenda al mapa
paleta_colores.caption = 'Centros de salud por cantón'
paleta_colores.add_to(mapa)

# Agregar el control de capas al mapa
folium.LayerControl().add_to(mapa)

# Mostrar el mapa
st.subheader('Cantidad de centros de salud cercanos a la ruta migratoria por cantón')

# Forma antigua
folium_static(mapa)


