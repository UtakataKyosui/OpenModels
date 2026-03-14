use sea_orm::entity::prelude::*;

#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel)]
#[sea_orm(table_name = "users")]
pub struct Model {
    // OpenModels: generated = database
    #[sea_orm(primary_key, auto_increment = false, column_type = "Uuid")]
    pub id: Uuid,
    #[sea_orm(column_type = "String(StringLen::N(255))")]
    pub email: String,
    #[sea_orm(column_type = "String(StringLen::N(120))")]
    pub display_name: String,
    #[sea_orm(column_type = "String(StringLen::N(255))")]
    pub password_hash: String,
    // OpenModels: generated = database
    #[sea_orm(column_type = "TimestampWithTimeZone")]
    pub created_at: DateTimeWithTimeZone,
}

// OpenModels Phase 2 keeps canonical relations for Phase 3 generation.
// Planned canonical relations:
// - posts: hasMany Post via authorId -> id

// OpenModels Phase 2 does not emit indexes or non-primary constraints yet.
// Planned indexes:
// - users_email_key: unique [email]
// Planned constraints:
// - users_email_unique: unique [email]

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

impl ActiveModelBehavior for ActiveModel {}
