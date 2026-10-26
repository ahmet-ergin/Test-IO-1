package com.amts.sampleapp

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast

class HomeActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_home)
        findViewById<Button>(R.id.transferButton).setOnClickListener {
            startActivity(Intent(this, FormActivity::class.java))
        }
        findViewById<Button>(R.id.longPressButton).setOnLongClickListener {
            Toast.makeText(this, "Long press", Toast.LENGTH_SHORT).show()
            true
        }
        val items = (1..60).map { "Synthetic item $it" }
        findViewById<ListView>(R.id.itemList).adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, items)
    }
}

class FormActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_form)
        findViewById<Button>(R.id.continueButton).setOnClickListener {
            val name = findViewById<EditText>(R.id.nameInput).text.toString()
            startActivity(Intent(this, ResultActivity::class.java).putExtra("name", name))
        }
    }
}

class ResultActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_result)
        findViewById<TextView>(R.id.resultText).text = "Completed for: " + intent.getStringExtra("name")
    }
}
