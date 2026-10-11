from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    image_score_threshold: float = Field(
        default=0.25,
        description=(
            "Минимальное косинусное сходство «текст запроса — изображение» (для CLIP ViT-B/32 "
            "совпадение ≈ 0.28–0.35, посторонние ≈ 0.20–0.25). Подбирается под модель"
        ),
    )
    prefetch_limit: PositiveInt = Field(
        default=200, description="Кандидатов из каждого вида поиска до слияния RRF"
    )

    autotag_temperature: float = Field(
        default=100.0,
        description="Масштаб логитов CLIP: вероятности тегов = softmax(temperature * cos) по словарю",
    )
    autotag_min_probability: float = Field(default=0.15, ge=0, le=1, description="Порог вероятности тега")
    autotag_min_similarity: float = Field(
        default=0.22,
        description="Минимальное абсолютное сходство: иначе softmax назначит теги любой картинке",
    )
    autotag_max_tags: PositiveInt = Field(default=5, description="Не больше автотегов на актив")
    autotag_prompt_template: str = Field(
        default="фото: {tag}", description="Шаблон текста тега для эмбеддинга"
    )
