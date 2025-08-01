import requests
import time
import json
import re
import sys
import csv
from datetime import datetime

def sql_escape(s):
    return s.replace("'", "''")  # Escape single quotes for SQL

def safe_sql_value(value):
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"  # Escape single quotes for SQL
    else:
        return f"'{value}'"

def fetch_and_save_authorLists(filename):
    
    # Step 1: Call the API to get list of authors
    url = "https://openlibrary.org/search/authors.json?q=*&limit=1000"
    response = requests.get(url)
    
    # Check for HTTP status code
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        print(response.text)  # Optional: see what was returned
        return
    
    try:
        data = response.json()
    except Exception as e:
        print("Failed to parse JSON response:")
        print(response.text[:200])  # Print part of the response to help debug
        raise e


    author_keys = []
    # Step 2: Loop through author IDs and call the detailed API
    for author in data.get('docs', []):
        key  = author.get('key')  # Format: OL12345A
        if key:
            author_keys.append(key)
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for key in author_keys:
            writer.writerow([key])

    print(f"Saved {len(author_keys)} author IDs to {filename}")

def generate_authorInsert(filename):

    # Step 1: Read list of authors
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        author_ids = [row[0] for row in reader]

    # Step 2: Generate SQL INSERT statements
    sql_statements = []
    book_statements = []
    coversFullList = []
    count = 0
    author_book_roles = set()
    subject_entries = set()
    subjectXBooks = set()
    coverBookStatements = []

    # Step 2: Loop through author IDs and call the detailed API
    for author_id in author_ids:
        
        if not author_id:
            continue

        # Extract ID and build the detailed URL
        author_url = f"https://openlibrary.org/authors/{author_id}.json"

        # Request detailed author data
        try:
            author_response = requests.get(author_url)
            author_data = author_response.json()

            # Example: Print or process detailed fields
            name = author_data.get('name', 'Unknown')
            entity_type = author_data.get('entity_type',None)
            personal_name = author_data.get('personal_name',None)
            title = author_data.get('title',None)

            birth_date_raw = author_data.get('birth_date', None)
            birth_year = None
            if birth_date_raw:
                match = re.search(r'(\d{4})', birth_date_raw)
                if match:
                    birth_year = int(match.group(1))

            death_date_raw = author_data.get('death_date', None)
            death_year = None
            if death_date_raw:
                match = re.search(r'(\d{4})', death_date_raw)
                if match:
                    death_year = int(match.group(1))

            bio = author_data.get('bio')
            if isinstance(bio, dict):  # bio can sometimes be a dict with a 'value'
                bio = bio.get('value', None)
            elif not isinstance(bio, str):
                bio = None

            key = author_data.get('key',None)
            alternate_names = author_data.get('alternate_names',[])
            if not isinstance(alternate_names,list):
                alternate_names = []

            created = author_data.get('created')
            if isinstance(created,dict):
                created = created.get('value',None)
                created = datetime.fromisoformat(created)
            else:
                created = None

            last_modified = author_data.get('last_modified')
            if isinstance(last_modified,dict):
                last_modified = last_modified.get('value',None)
                last_modified = datetime.fromisoformat(last_modified)
            else:
                last_modified = None


            name_sql = f"'{sql_escape(name)}'" if name else "NULL"
            bio_sql = safe_sql_value(bio)
            entity_type_sql = safe_sql_value(entity_type)

            birth_date_raw_sql = f"'{sql_escape(birth_date_raw)}'" if birth_date_raw else "NULL"
            birth_year_sql = str(birth_year) if birth_year is not None else "NULL"
            death_date_raw_sql = f"'{sql_escape(death_date_raw)}'" if death_date_raw else "NULL"
            death_year_sql = str(death_year) if death_year is not None else "NULL"

            created_sql = f"'{created.isoformat(sep=' ')}'" if created else "NULL"
            last_modified_sql = f"'{last_modified.isoformat(sep=' ')}'" if last_modified else "NULL"

            title_sql = f"'{sql_escape(title)}'" if title else "NULL"
            personal_name_sql = f"'{sql_escape(personal_name)}'" if personal_name else "NULL"
            alternate_names_sql = safe_sql_value(json.dumps(alternate_names) if alternate_names else None)
            key_sql = f"'{sql_escape(key)}'" if key else "NULL"

            sql = f"""INSERT INTO public."Author" (
                "AuthorID", name, bio, entity_type, birth_date, birth_year,
                personal_name, death_date, death_year, title, alternate_names,
                keyVal, created, last_modified
            ) VALUES (
                '{author_id}', {name_sql}, {bio_sql}, {entity_type_sql},
                {birth_date_raw_sql}, {birth_year_sql}, {personal_name_sql}, {death_date_raw_sql}, 
                {death_year_sql}, {title_sql}, {alternate_names_sql}, {key_sql}, {created_sql},
                {last_modified_sql}
            );"""
            sql_statements.append(sql)

            time.sleep(45)
            url_authorWorks = f"https://openlibrary.org/authors/{author_id}/works.json"
            
            authorWorks_response = requests.get(url_authorWorks)
            authorWorks_data = authorWorks_response.json()
            
            for workOfAuthor in authorWorks_data.get('entries', []):
                key = workOfAuthor.get('key',None)
                work_id = key.split('/')[-1]

                title = workOfAuthor.get('title',None)
                description = workOfAuthor.get('description',None)
                if isinstance(description, dict):  # bio can sometimes be a dict with a 'value'
                    description = description.get('value', None)
                elif not isinstance(description, str):
                    description = None

                createdB = workOfAuthor.get('created')
                if isinstance(createdB,dict):
                    createdB = createdB.get('value',None)
                    createdB = datetime.fromisoformat(createdB)
                else:
                    createdB = None

                last_modifiedB = workOfAuthor.get('last_modified')
                if isinstance(last_modifiedB,dict):
                    last_modifiedB = last_modifiedB.get('value',None)
                    last_modifiedB = datetime.fromisoformat(last_modifiedB)
                else:
                    last_modifiedB = None

                first_publish_date = workOfAuthor.get('first_publish_date',None)
                fPublish_year = None
                if first_publish_date:
                    match = re.search(r'(\d{4})', first_publish_date)
                    if match:
                        fPublish_year = int(match.group(1))

                #Subject
                for desc in workOfAuthor.get('subject_places',[]):
                    subject_entries.add(('place',desc))
                    subjectXBooks.add((work_id,('place',desc)))

                for desc in workOfAuthor.get('subjects', []):
                    subject_entries.add(('topic', desc))
                    subjectXBooks.add((work_id,('topic',desc)))

                for desc in workOfAuthor.get('subject_people', []):
                    subject_entries.add(('people', desc))
                    subjectXBooks.add((work_id,('people',desc)))

                for desc in workOfAuthor.get('subject_times', []):
                    subject_entries.add(('time', desc))
                    subjectXBooks.add((work_id,('time',desc)))

                #Cover Data
                coverList = workOfAuthor.get('covers',None)
                if not isinstance(coverList,list):
                    coverList = None
                else:
                    for cover in coverList:
                        coversFullList.append(cover)
                        coverBookStatements.append((work_id,cover))

                #Book's author data
                authorsxBookL = workOfAuthor.get('authors',None)
                if not isinstance(authorsxBookL,list):
                    authorsxBookL = None
                
                if authorsxBookL:
                    for authorxBook in authorsxBookL:
                        authorFull = authorxBook.get('author',None)
                        authorFull = authorFull.get('key',None)
                        authorV = authorFull.split('/')[-1]
                        typeRole = authorxBook.get('type',None)
                        if isinstance(typeRole, dict):
                            type_key = typeRole.get('key', None)
                        elif isinstance(typeRole, str):
                            type_key = typeRole 
                        #typeRole = typeRole.get('key',None)
                        typeV = type_key.split('/')[-1]

                        if authorV is not None:
                            triplet = (authorV,work_id,typeV)

                            if triplet not in author_book_roles:
                                author_book_roles.add(triplet)

                createdB_sql = f"'{createdB.isoformat(sep=' ')}'" if createdB else "NULL"
                last_modifiedB_sql = f"'{last_modifiedB.isoformat(sep=' ')}'" if last_modifiedB else "NULL"
                first_publish_date = f"'{sql_escape(first_publish_date)}'" if first_publish_date else "NULL"
                fPublish_year = str(fPublish_year) if fPublish_year is not None else "NULL"
                description = safe_sql_value(description)
                title = f"'{sql_escape(title)}'" if title else "NULL"


                book_sql = f"""INSERT INTO public."Book" (
                    "BookID", title, description, first_publish_date, first_publish_year,
                    created, last_modified
                ) VALUES (
                    '{work_id}', {title}, {description}, {first_publish_date},
                    {fPublish_year}, {createdB_sql}, {last_modifiedB_sql}
                );"""
                book_statements.append(book_sql)

            

        except Exception as e:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno
            print(f"Failed to fetch data for author {author_id}: {e} (on line {line_number})")

        time.sleep(1)  # Be nice to the API by not spamming requests

    # Step 3: Save to a .sql file (optional)
    with open('insert_authors.sql', 'w', encoding='utf-8') as f:
        for statement in sql_statements:
            f.write(statement + '\n')

    generate_coverScript(coversFullList,coverBookStatements)
    generate_booksByScript(book_statements)
    generate_booksByAuthor(author_book_roles)
    generate_subjectScript(subject_entries,subjectXBooks)
    print("Generated SQL statements saved to insert_authors.sql")

def generate_coverScript(coversFullList,coverBookStatements):
    coversFullList = list(set(coversFullList))
    coverBookStatements = list(set(coverBookStatements))
    with open('insert_covers.sql', 'w', encoding='utf-8') as f:
        for cover in coversFullList:
            sql_CoverBook = f"""INSERT INTO public."Cover" ("CoverID") VALUES ({cover});"""
            f.write(sql_CoverBook + '\n')

    with open('inser_bookCover.sql','w',encoding='utf-8') as f:
        for (work_id,cover) in coverBookStatements:
            sql_CoverBook = f"""INSERT INTO public."BooksCover" ("BookID", "CoverID") 
                                        VALUES ('{work_id}',{cover});"""
            f.write(sql_CoverBook + '\n')

def generate_booksByScript(book_statements):
    with open('insert_books.sql','w',encoding='utf-8') as f:
        for statement in book_statements:
            f.write(statement + '\n')

def generate_booksByAuthor(author_book_roles):
    
    with open('insert_bookAuthors.sql', 'w', encoding='utf-8') as f:
        for author_id, book_id, role in author_book_roles:
            sql_authorxBook = f"""INSERT INTO public."BooksAuthors" ("AuthorID", "BookID", rol_type) 
                                VALUES ('{author_id}', '{book_id}', '{role}');"""
            f.write(sql_authorxBook + '\n')


def generate_subjectScript(subject_entries,subjectXBooks):
    subject_id_map = {}
    subject_id = 0  # or resume from max id if you're appending

    with open('insert_subjects.sql', 'w', encoding='utf-8') as f:
        for subject_type, description in sorted(subject_entries):
            description_sql  = f"'{sql_escape(description)}'" if description else "NULL"
            sql = f"""INSERT INTO public."Subjects" ("SubjectID", subj_type, description)  
                    VALUES ({subject_id}, '{subject_type}', {description_sql});"""
            f.write(sql + '\n')
            
            subject_id_map[(subject_type, description)] = subject_id
            subject_id += 1

    with open('insert_subjectXBook.sql','w',encoding='utf-8') as f:
        for work_id, (stype, sdesc) in subjectXBooks:
            sid = subject_id_map[(stype, sdesc)]
            sql = f"""INSERT INTO public."BookSubjects" ("BookID", "SubjectID") VALUES ('{work_id}', {sid});"""
            f.write(sql + '\n')

filename = "author_ids.csv"
#fetch_and_save_authorLists(filename)
generate_authorInsert(filename)