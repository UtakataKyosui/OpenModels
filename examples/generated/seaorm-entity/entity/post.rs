use sea_orm::entity::prelude::*;

#[derive(Copy, Clone, Debug, PartialEq, Eq, EnumIter, DeriveActiveEnum)]
#[sea_orm(rs_type = "String", db_type = "String(StringLen::N(32))", enum_name = "post_status")]
pub enum PostStatus {
    #[sea_orm(string_value = "draft")]
    Draft,
    #[sea_orm(string_value = "published")]
    Published,
    #[sea_orm(string_value = "archived")]
    Archived,
}

#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel)]
#[sea_orm(table_name = "posts")]
pub struct Model {
    // OpenModels: generated = database
    #[sea_orm(primary_key, auto_increment = false, column_type = "Uuid")]
    pub id: Uuid,
    #[sea_orm(column_type = "Uuid")]
    pub author_id: Uuid,
    #[sea_orm(column_type = "String(StringLen::N(200))")]
    pub title: String,
    #[sea_orm(column_type = "Text")]
    pub body: String,
    // OpenModels: default = "draft"
    #[sea_orm(column_type = "String(StringLen::N(32))")]
    pub status: PostStatus,
    // OpenModels: generated = application
    // OpenModels: computed = slugify(title)
    #[sea_orm(column_type = "String(StringLen::N(240))")]
    pub slug: String,
    // OpenModels: generated = database
    #[sea_orm(column_type = "TimestampWithTimeZone")]
    pub created_at: DateTimeWithTimeZone,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(belongs_to = "super::user::Entity", from = "Column::AuthorId", to = "super::user::Column::Id", on_update = "Cascade", on_delete = "Cascade")]
    Author,
}

impl Related<super::user::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Author.def()
    }
}

// OpenModels Phase 3 does not emit indexes or non-foreign-key constraints yet.
// Planned indexes:
// - posts_author_created_at_idx: [authorId, createdAt]
// Planned constraints:
// - posts_slug_nonempty: check (slug <> '')

impl ActiveModelBehavior for ActiveModel {}
