from api_connection.api_connection import get_police_data

df = get_police_data()
print(df.head())
print(df.shape)
