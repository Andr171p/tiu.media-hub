from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    image_score_threshold: float = Field(
        default=0.05,
        description=(
            "Минимальное косинусное сходство «текст запроса — изображение». "
            "Ниже — результат считается нерелевантным. Подбирается под модель"
        ),
    )
    prefetch_limit: PositiveInt = Field(
        default=200, description="Кандидатов из каждого вида поиска до слияния RRF"
    )

    autotag_logit_scale: float = Field(
        default=110.0,
        description="Масштаб логитов SigLIP: вероятность тега = sigmoid(scale * cos + bias)",
    )
    autotag_logit_bias: float = Field(default=-12.0, description="Смещение логитов SigLIP")
    autotag_min_probability: float = Field(default=0.3, ge=0, le=1, description="Порог назначения автотега")
    autotag_max_tags: PositiveInt = Field(default=8, description="Не больше автотегов на актив")
    autotag_prompt_template: str = Field(
        default="фотография: {tag}",
        description="Шаблон текста тега для эмбеддинга",
    )
