"""测试变量数据校验"""
import sys
import asyncio

sys.path.insert(0, "backend")

from app.services.ai_service import validate_variable_data


async def main():
    variables = [
        {"key": "company_name", "value": ""},
        {"key": "sign_date", "value": "2024/13/01"}
    ]
    
    validation_rules = {}
    
    result = await validate_variable_data(variables, validation_rules)
    print("校验结果：")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())