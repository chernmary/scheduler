<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>График сотрудников</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f9f9f9;
            margin: 0;
            padding: 0;
            color: #333;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 20px;
            background-color: #fff;
            box-shadow: 0 0 10px rgba(0,0,0,0.05);
        }
        .login-form input {
            padding: 4px;
            margin-right: 4px;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
        .login-form button {
            background-color: #4CAF50;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        h1 {
            text-align: center;
            margin: 20px 0;
        }
        table {
            border-collapse: collapse;
            width: 95%;
            margin: 20px auto;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 0 10px rgba(0,0,0,0.05);
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }
        th {
            background-color: #f0f0f0;
            font-weight: bold;
        }
        select {
            padding: 4px;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
        .button-container {
            text-align: center;
            margin: 20px;
        }
        .generate-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 18px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .generate-btn:hover {
            background-color: #45a049;
        }
    </style>
</head>
<body>

<header>
    <div><strong>График сотрудников</strong></div>
    <div>
        {% if is_admin %}
            <form method="get" action="/logout" class="login-form" style="display:inline;">
                <button type="submit">Выйти</button>
            </form>
        {% else %}
            <form method="post" action="/login" class="login-form" style="display:inline;">
                <input name="username" placeholder="Логин">
                <input name="password" type="password" placeholder="Пароль">
                <button type="submit">Войти</button>
            </form>
        {% endif %}
    </div>
</header>

<table>
    <thead>
        <tr>
            <th>Локация</th>
            {% for date_str in dates %}
                <th>{{ date_str }}</th>
            {% endfor %}
        </tr>
    </thead>
    <tbody>
        {% for loc_name, row in schedule_data.items() %}
            <tr>
                <td>{{ loc_name }}</td>
                {% for emp_name in row %}
                    <td>
                        {% if is_admin %}
                            <form method="post" action="/schedule/update">
                                <input type="hidden" name="date_str" value="{{ raw_dates[loop.index0] }}">
                                <input type="hidden" name="location_id" value="{{ locations_map[loc_name] }}">
                                <select name="employee_id" onchange="this.form.submit()">
                                    <option value="">-- пусто --</option>
                                    {% for emp in employees %}
                                        <option value="{{ emp.id }}" {% if emp_name == emp.full_name %}selected{% endif %}>
                                            {{ emp.full_name }}
                                        </option>
                                    {% endfor %}
                                </select>
                            </form>
                        {% else %}
                            {{ emp_name }}
                        {% endif %}
                    </td>
                {% endfor %}
            </tr>
        {% endfor %}
    </tbody>
</table>

{% if is_admin %}
<div class="button-container">
    <form method="post" action="/schedule/generate">
        <button type="submit" class="generate-btn">Сгенерировать график</button>
    </form>
</div>
{% endif %}

</body>
</html>
