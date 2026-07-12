from string import Formatter


class PromptRenderer:
    @staticmethod
    def render(template: str, **kwargs) -> str:
        return template.format(**kwargs)

    @staticmethod
    def get_variables(template: str) -> set[str]:
        return {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name
        }
