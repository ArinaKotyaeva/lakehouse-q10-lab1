import streamlit as st
import pandas as pd
import trino
st.set_page_config(page_title="Q10 Lakehouse", layout="wide")
st.title("Lakehouse · Возвращённые товары")
st.caption("Вариант 2 · TPC-H Q10 · sf1")
def query(sql):
    with trino.dbapi.connect(host="trino", port=8080, user="bi", catalog="lakehouse") as conn:
        cur=conn.cursor(); cur.execute(sql)
        return pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
layer=st.radio("Слой данных", ["Bronze", "Gold"], horizontal=True)
try:
    if layer == "Bronze":
        st.subheader("Исходные данные Bronze")
        table=st.selectbox("Таблица", ["customer", "orders", "lineitem", "nation"])
        sql=f"SELECT * FROM lakehouse.bronze.{table} LIMIT 100"
        st.code(sql, language="sql"); st.dataframe(query(sql), use_container_width=True)
        sql="""SELECT n.name AS nation, sum(l.extendedprice*(1-l.discount)) AS revenue
FROM lakehouse.bronze.customer c
JOIN lakehouse.bronze.nation n ON c.nationkey=n.nationkey
JOIN lakehouse.bronze.orders o ON o.custkey=c.custkey
JOIN lakehouse.bronze.lineitem l ON l.orderkey=o.orderkey
WHERE o.orderdate >= DATE '1993-10-01' AND o.orderdate < DATE '1994-01-01'
AND l.returnflag='R' GROUP BY n.name ORDER BY revenue DESC"""
        st.subheader("Выручка возвращённых позиций по странам — из Bronze")
        st.code(sql, language="sql")
        df=query(sql); st.bar_chart(df.set_index("nation")); st.dataframe(df)
    else:
        st.subheader("Топ-20 клиентов · Gold")
        df=query("SELECT * FROM lakehouse.gold.returned_customers_top20 ORDER BY revenue DESC, custkey")
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("name")["revenue"])
except Exception as exc:
    st.error(f"Данные ещё не готовы или Trino недоступен: {exc}")
