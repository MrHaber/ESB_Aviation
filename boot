python run.py

// В database.py, нужно обновить модель данных

// Генерация JWT
curl -X POST -d "username=admin&password=25565" http://localhost:8000/api/v1/auth/token
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJvcGVyYXRvciIsImV4cCI6MTc1MDk0ODc1OH0.oJeLG5cKnilxbl5NtclV71ohOqGJwHJswbuavV67AkI","token_type":"bearer"}
// Пример POST запроса
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTcxOTQ2MjQ1NX0.YourTokenSignatureHere" http://localhost:8000/api/v1/plugins

// Принцип выдачи роли в JWT очень простой: имя пользователя = его роли

username=admin role=admin
username=integrator role=integrator
