from openai import OpenAI

# 1. 初始化客户端 (使用硅基流动的免费接口)
client = OpenAI(
    api_key="sk-xiddgqubhzwfmpsgqjlwsxsxhjjfspkfwmkawqeflsxlgmmc",
    base_url="https://api.siliconflow.cn/v1"
)

# 2. 定义一个简单的测试问题
prompt = "你好，请简短回答：企业客户故障补偿判断中，如果证据不足应该返回什么状态？"

# 3. 调用模型 (使用免费的 Qwen2.5-7B-Instruct)
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[
        {"role": "system", "content": "你是一个企业故障补偿审核专家。"},
        {"role": "user", "content": prompt}
    ],
    max_tokens=100
)

# 4. 打印结果
print("模型回答：", response.choices[0].message.content)