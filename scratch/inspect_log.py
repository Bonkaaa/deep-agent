import sys

class HumanMessage:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class AIMessage:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class ToolMessage:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)

def main():
    lines = open('logs/sanitizer-additionalFlowStep.log', encoding='utf-8').readlines()
    last_line = lines[-1]
    result_str = last_line.split('Result: ')[1]
    result = eval(result_str)
    messages = result['messages']
    m = messages[-1]
    print("--- Msg attributes ---")
    for k, v in m.__dict__.items():
        print(f"{k}: {str(v)[:1000]}")

if __name__ == '__main__':
    main()
