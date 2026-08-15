{#
    Override do macro padrão do dbt. Por padrão, um model com `+schema: marts`
    materializa em `<target_schema>_marts` (concatenado), não em `marts`.
    Aqui queremos schemas explícitos e exatos — staging, marts — sem prefixo
    do schema do target. Padrão documentado no próprio dbt para quem usa
    schema por camada em vez de por ambiente.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
