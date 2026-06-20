
//Basic commands
latest_db> db.students.insertMany([
...     {"name": "Zendaya", "age": 25},
...     {"name": "Millie Bobby Brown", "age": 18},
...     {"name": "Elle Fanning", "age": 23},
...     {"name": "Amandla Stenberg", "age": 23},
...     {"name": "Chloe Grace Moretz", "age": 24},
...     {"name": "Lily-Rose Depp", "age": 22},
...     {"name": "Hailee Steinfeld", "age": 25},
...     {"name": "Kiernan Shipka", "age": 22},
...     {"name": "Yara Shahidi", "age": 21}
... ]);
latest_db> db.students.updateMany({},{$set:{hobbies:["Anime","Movie","Web-Series"]}})
// Nested Documents : Max size of nested document/records under a sigle document/record is 16 MB
latest_db> db.students.updateOne({"name":"Margot"},{$set:{idCards:{hasPan:false,hasAadhar:true}}})
/*{
    _id: ObjectId('667e4d0eb634173492149f48'),
    name: 'Margot',
    age: 22,
    idCards: { hasPan: false, hasAadhar: true },
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  }*/
// Not Nested
latest_db> db.students.updateOne({age:18},{$set:{hasPan:false,hasAadhar:false}})
/*  {
    _id: ObjectId('667e4db9b634173492149f4a'),
    name: 'Millie Bobby Brown',
    age: 18,
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ],
    hasAadhar: false,
    hasPan: false
  }*/
// Filter - Nested Documents
latest_db> db.students.find({"idCards.hasAadhar":true})
/*[
  {
    _id: ObjectId('667e4d0eb634173492149f48'),
    name: 'Margot',
    age: 22,
    idCards: { hasPan: false, hasAadhar: true },
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  },
  {
    _id: ObjectId('667e4db9b634173492149f4b'),
    name: 'Elle Fanning',
    age: 23,
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ],
    idCards: { hasPan: true, hasAadhar: true }
  }
]*/
// find() returns a cursor - we can iterate it but findOne() return null if record not present
latest_db> db.students.find().forEach((x) => {printjson(x)})
// get only 3 documents - 20< age < 23
latest_db> db.students.find({age:{$gt:20,$lt:23}}).limit(3).toArray()
/*[
  {
    _id: ObjectId('667e4d0eb634173492149f48'),
    name: 'Margot',
    age: 22,
    idCards: { hasPan: false, hasAadhar: true },
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  },
  {
    _id: ObjectId('667e4db9b634173492149f4e'),
    name: 'Lily-Rose Depp',
    age: 22,
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  },
  {
    _id: ObjectId('667e4db9b634173492149f50'),
    name: 'Kiernan Shipka',
    age: 22,
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  }
]*/
// Filter - ObjectId
latest_db> db.students.find({"_id":ObjectId('667e4db9b634173492149f50')})
/*[
  {
    _id: ObjectId('667e4db9b634173492149f50'),
    name: 'Kiernan Shipka',
    age: 22,
    hobbies: [ 'Anime', 'Movie', 'Web-Series' ]
  }
]*/
